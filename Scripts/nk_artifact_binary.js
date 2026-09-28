/** Claude artifacts serve only web file types, so the binary assets (.glb .ktx2 .hdr) are published as base64
 *  text next to the page (<name>.b64.txt) and decoded here. Built by Scripts/nk_artifact.py. */
const SIZES = /*SIZES*/{};  // base64 length per asset, for the progress bar

const LUT = new Uint8Array(128);
for (let i = 0; i < 64; i++) LUT['ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'.charCodeAt(i)] = i;

// Base64 (ASCII bytes, one line) -> ArrayBuffer, without building a JS string of the whole file.
function decode(b64) {
  let n = b64.length;
  while (n > 0 && (b64[n - 1] === 61 || b64[n - 1] <= 32)) n--;  // '=' padding, trailing newline
  const out = new Uint8Array((n * 3) >> 2), end = n - (n % 4);
  let o = 0, i = 0;
  for (; i < end; i += 4) {
    const v = LUT[b64[i]] << 18 | LUT[b64[i + 1]] << 12 | LUT[b64[i + 2]] << 6 | LUT[b64[i + 3]];
    out[o++] = v >> 16; out[o++] = v >> 8 & 255; out[o++] = v & 255;
  }
  if (n - i >= 2) {
    const v = LUT[b64[i]] << 18 | LUT[b64[i + 1]] << 12 | (n - i === 3 ? LUT[b64[i + 2]] << 6 : 0);
    out[o++] = v >> 16; if (n - i === 3) out[o++] = v >> 8 & 255;
  }
  return out.buffer;
}

/** fetchBinary('./assets/x.glb') reads ./assets/x.glb.b64.txt; onProgress gets {loaded, total} like three.js loaders. */
export async function fetchBinary(url, onProgress) {
  const response = await fetch(`${url}.b64.txt`);
  if (!response.ok) throw new Error(`${url} could not be read (HTTP ${response.status}).`);
  if (!onProgress || !response.body) return decode(new Uint8Array(await response.arrayBuffer()));
  const total = SIZES[url.replace(/^\.\//, '')] || 0, reader = response.body.getReader(), parts = [];
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); loaded += value.length; onProgress({ loaded, total: Math.max(total, loaded) });
  }
  const bytes = new Uint8Array(loaded);
  let at = 0;
  for (const part of parts) { bytes.set(part, at); at += part.length; }
  return decode(bytes);
}

/** GLTFLoader hands the model's embedded KTX2 textures to KTX2Loader as blob: URLs, which FileLoader would
 *  fetch(). The artifact frame may not allow fetching blob: URLs, so those Blobs are read directly. */
export function readBlobUrls(THREE) {
  const blobs = new Map(), create = URL.createObjectURL, revoke = URL.revokeObjectURL;
  URL.createObjectURL = object => { const url = create.call(URL, object); if (object instanceof Blob) blobs.set(url, object); return url; };
  URL.revokeObjectURL = url => { blobs.delete(url); revoke.call(URL, url); };
  const load = THREE.FileLoader.prototype.load;
  THREE.FileLoader.prototype.load = function (url, onLoad, onProgress, onError) {
    const blob = typeof url === 'string' && url.startsWith('blob:') && blobs.get(url);
    if (!blob) return load.call(this, url, onLoad, onProgress, onError);
    const type = this.responseType;
    this.manager.itemStart(url);
    (type === 'arraybuffer' ? blob.arrayBuffer() : type === 'blob' ? Promise.resolve(blob)
      : blob.text().then(text => type === 'json' ? JSON.parse(text) : text))
      .then(data => { onLoad?.(data); this.manager.itemEnd(url); })
      .catch(error => { if (onError) onError(error); else console.error(error); this.manager.itemError(url); this.manager.itemEnd(url); });
  };
}
