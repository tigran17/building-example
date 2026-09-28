"""Local web server for the New Komitas 3D site.

python3 Scripts/serve.py [port] [root] [--lan]      default: 8770, ./Website  ->  http://localhost:8770

--lan   also serve on this Mac's Wi-Fi address so a phone on the same network can open the site;
        prints the address and a QR code to scan. Without it only this Mac can connect.

<address>/?bench on a phone measures it (a 16 s orbit) and POSTs the result to /__report, saved as
JSON in Web-Build/device-reports/ (max 256 KB each, 500 files) and summarised in this Terminal.

Every response is revalidated (Cache-Control: no-cache + Last-Modified), so a rebuilt model is picked
up on the next reload while unchanged files come back as a quick 304 instead of a re-download (this
matters on phones). JSON, JS, CSS and HTML are gzip-compressed (the apartment/traffic/tree data shrink ~6x).
"""
import email.utils
import gzip
import http.server
import io
import json
import os
import re
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GZIP_TYPES = {'.js', '.json', '.css', '.html', '.svg', '.webmanifest', '.txt'}
REPORTS = os.environ.get('NK_REPORTS') or os.path.join(os.path.dirname(HERE), 'Web-Build', 'device-reports')
_gz_cache = {}


def device_label(ua):
    for pattern, name in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'), ('Macintosh', 'Mac'),
                          ('Windows', 'Windows'), ('Linux', 'Linux')):
        if pattern in ua:
            return name
    return 'device'


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.glb': 'model/gltf-binary', '.hdr': 'application/octet-stream', '.wasm': 'application/wasm',
                      '.js': 'text/javascript', '.webp': 'image/webp', '.json': 'application/json',
                      '.ktx2': 'image/ktx2', '.webmanifest': 'application/manifest+json'}

    def send_head(self):
        path = self.translate_path(self.path)
        if (os.path.isfile(path) and os.path.splitext(path)[1] in GZIP_TYPES
                and 'gzip' in self.headers.get('Accept-Encoding', '')):
            st = os.stat(path)
            since = self.headers.get('If-Modified-Since')
            if since:
                try:
                    if email.utils.parsedate_to_datetime(since).timestamp() >= int(st.st_mtime):
                        self.send_response(304)
                        self.end_headers()
                        return None
                except (TypeError, ValueError, IndexError, OverflowError):
                    pass
            key = (path, st.st_mtime_ns)
            data = _gz_cache.get(key)
            if data is None:
                with open(path, 'rb') as f:
                    data = _gz_cache[key] = gzip.compress(f.read(), 6)
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(path))
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Last-Modified', self.date_time_string(st.st_mtime))
            self.send_header('Vary', 'Accept-Encoding')
            self.end_headers()
            return io.BytesIO(data)
        return super().send_head()

    def do_POST(self):
        """Device benchmark results from ?bench (small JSON only, into Web-Build/device-reports)."""
        if self.path.split('?')[0] != '/__report':
            self.send_error(404)
            return
        size = int(self.headers.get('Content-Length') or 0)
        if not 0 < size <= 256_000:
            self.send_error(413)
            return
        try:
            data = json.loads(self.rfile.read(size))
            assert isinstance(data, dict)
        except (ValueError, AssertionError):
            self.send_error(400)
            return
        os.makedirs(REPORTS, exist_ok=True)
        if len(os.listdir(REPORTS)) >= 500:
            self.send_error(507)
            return
        orbit = data.get('orbit') or {}
        label = device_label(str(orbit.get('userAgent', '')))
        data['received'] = {'from': self.client_address[0], 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{re.sub('[^A-Za-z0-9]', '', label)}.json"
        with open(os.path.join(REPORTS, name), 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Device report from {label}: {orbit.get('medianFps')} fps median, slowest 5% {orbit.get('p95FrameMs')} ms, "
              f"ready after {data.get('readyMs')} ms ({data.get('gpu')}) -> Web-Build/device-reports/{name}", flush=True)
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *args):
        pass


def lan_address():
    """The Mac's address on the local network (a UDP 'connect' sends nothing)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def print_qr(text):
    sys.path.insert(0, HERE)
    from qrcodegen import QrCode   # Project Nayuki, MIT licence
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    n, pad = qr.get_size(), 2
    dark = lambda x, y: 0 <= x < n and 0 <= y < n and qr.get_module(x, y)
    for y in range(-pad, n + pad, 2):
        row = ''.join('█' if dark(x, y) and dark(x, y + 1) else '▀' if dark(x, y) else '▄' if dark(x, y + 1) else ' '
                      for x in range(-pad, n + pad))
        print('  \x1b[30;47m' + row + '\x1b[0m')     # black on white, readable on dark terminals too


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    lan = '--lan' in sys.argv
    port = int(args[0]) if args else 8770
    root = args[1] if len(args) > 1 else os.path.join(os.path.dirname(HERE), 'Website')
    os.chdir(root)

    class Server(http.server.ThreadingHTTPServer):
        request_queue_size = 128      # the page fires a dozen parallel asset requests
        daemon_threads = True

    try:
        server = Server(('0.0.0.0' if lan else '127.0.0.1', port), Handler)
    except OSError as error:
        sys.exit(f'Port {port} is already in use ({error.strerror}). Close the other "Start 3D Site" Terminal window '
                 f'(Ctrl+C there), then start this one again.')
    print(f'New Komitas 3D: http://localhost:{port}  (serving {root}; Ctrl+C to stop)', flush=True)
    if lan:
        ip = lan_address()
        if ip:
            url = f'http://{ip}:{port}/'
            print(f'\nOn a phone or tablet on the same Wi-Fi, open  {url}\nor scan this code with the camera:\n')
            print_qr(url)
            print(f'\nTo measure a phone\'s speed, open  {url}?bench  (results appear here and in Web-Build/device-reports).')
            print('\nIf macOS asks whether Python may accept incoming connections, choose Allow.', flush=True)
        else:
            print('No Wi-Fi/LAN address found; only this Mac can open the site.', flush=True)
    server.serve_forever()
