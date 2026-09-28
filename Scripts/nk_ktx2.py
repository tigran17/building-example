"""Re-encode every texture of a GLB as KTX2 / Basis Universal (KHR_texture_basisu).

Phones keep compressed textures compressed on the GPU: a 2048 px lightmap needs ~2.8 MB of GPU memory
as ETC1S (ASTC/ETC2/BC7 after transcoding) instead of ~22 MB as a decoded JPEG, and nothing is decoded
on the main thread. ETC1S at quality 100 measured 34 dB PSNR against the JPEG lightmaps (visually
identical at 2x zoom) at about half the JPEG size.

python3 Scripts/nk_ktx2.py Website/assets/new-komitas-complex-mobile.glb Website/assets/new-komitas-complex-mobile-ktx2.glb
python3 Scripts/nk_ktx2.py --textures Website/assets/new-komitas-complex.glb Website/assets/lm
    (every texture as its own file + manifest.json: desktops open with the phone model and stream these in;
    the hero blocks stay JPEG: at 4096 px ETC1S tints large flat wall areas slightly, the neighbours and
    ground become KTX2)
Needs basisu (brew install basis_universal) and macOS sips.
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

BASISU = '/opt/homebrew/bin/basisu'
ARGS = ['-ktx2', '-etc1s', '-quality', '100', '-effort', '6', '-mipmap']


def read_glb(path):
    b = open(path, 'rb').read()
    magic, version, length = struct.unpack('<III', b[:12])
    assert magic == 0x46546C67 and version == 2, 'not a glTF 2.0 binary'
    jlen, jtype = struct.unpack('<II', b[12:20])
    doc = json.loads(b[20:20 + jlen])
    off = 20 + jlen
    blen, btype = struct.unpack('<II', b[off:off + 8])
    return doc, b[off + 8:off + 8 + blen]


def write_glb(path, doc, views):
    """views: list of bytes, one per bufferView (same order); re-laid out 8-byte aligned."""
    blob = bytearray()
    for i, data in enumerate(views):
        blob += b'\0' * (-len(blob) % 8)
        doc['bufferViews'][i]['byteOffset'] = len(blob)
        doc['bufferViews'][i]['byteLength'] = len(data)
        blob += data
    blob += b'\0' * (-len(blob) % 4)
    doc['buffers'] = [{'byteLength': len(blob)}]
    js = json.dumps(doc, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        f.write(struct.pack('<II', len(blob), 0x004E4942) + bytes(blob))


def encode(data, name, tmp):
    src = os.path.join(tmp, name + '.src')
    png = os.path.join(tmp, name + '.png')
    out = os.path.join(tmp, name + '.ktx2')
    open(src, 'wb').write(data)
    # basisu's JPEG reader rejects these files; go through a lossless PNG first
    subprocess.run(['sips', '-s', 'format', 'png', src, '--out', png], check=True, capture_output=True)
    subprocess.run([BASISU, *ARGS, '-output_file', out, png], check=True, capture_output=True)
    return open(out, 'rb').read()


def main(src, dst):
    doc, bin_ = read_glb(src)
    views = [bin_[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']] for v in doc['bufferViews']]
    images = doc.get('images', [])
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(3) as pool:
        jobs = {i: pool.submit(encode, views[im['bufferView']], f'img{i}', tmp) for i, im in enumerate(images)}
        for i, im in enumerate(images):
            data = jobs[i].result()
            print(f"  {im.get('name', i)}: {len(views[im['bufferView']]) / 1e6:.2f} MB -> {len(data) / 1e6:.2f} MB KTX2")
            views[im['bufferView']] = data
            im['mimeType'] = 'image/ktx2'
    for tex in doc.get('textures', []):
        if 'source' in tex:
            tex.setdefault('extensions', {})['KHR_texture_basisu'] = {'source': tex.pop('source')}
    for key in ('extensionsUsed', 'extensionsRequired'):
        doc[key] = sorted(set(doc.get(key, [])) | {'KHR_texture_basisu'})
    write_glb(dst, doc, views)
    print(f'{os.path.basename(src)} {os.path.getsize(src) / 1e6:.1f} MB -> {os.path.basename(dst)} {os.path.getsize(dst) / 1e6:.1f} MB')


KEEP_JPEG = ('A_Shell', 'B_Shell', 'A_Balconies', 'B_Balconies')


def textures(src, outdir):
    doc, bin_ = read_glb(src)
    os.makedirs(outdir, exist_ok=True)
    manifest, total = {}, 0
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(3) as pool:
        jobs = []
        for i, im in enumerate(doc.get('images', [])):
            v = doc['bufferViews'][im['bufferView']]
            data = bin_[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
            name = im.get('name') or f'image{i}'
            keep = any(k in name for k in KEEP_JPEG) and im.get('mimeType') == 'image/jpeg'
            jobs.append((name, data, None if keep else pool.submit(encode, data, f'img{i}', tmp)))
        for name, data, job in jobs:
            out, ext = (data, '.jpg') if job is None else (job.result(), '.ktx2')
            total += len(out)
            with open(os.path.join(outdir, name + ext), 'wb') as f:
                f.write(out)
            manifest[name] = name + ext
            print(f'  {name}: {len(data) / 1e6:.2f} MB -> {len(out) / 1e6:.2f} MB {ext[1:].upper()}')
    with open(os.path.join(outdir, 'manifest.json'), 'w') as f:
        json.dump({'source': os.path.basename(src), 'textures': manifest}, f, indent=1)
    print(f'{len(jobs)} textures -> {outdir} ({total / 1e6:.1f} MB)')


if __name__ == '__main__':
    if sys.argv[1] == '--textures':
        textures(*sys.argv[2:4])
    else:
        main(*sys.argv[1:3])
