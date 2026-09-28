"""Package Website/ as a shareable Claude Artifact (a claude.ai link anyone can open once it is shared).

    python3 Scripts/nk_artifact.py [SHARE_BASE]     -> Web-Build/artifact/ + Web-Build/artifact-files.json

Then ask Claude to publish Web-Build/artifact/index.html with root Web-Build/artifact and the files listed in
artifact-files.json, to the existing URL (ARTIFACT_URL). The LAN site in Website/ is not changed.

What the artifact frame needs (checked on frame.claudeusercontent.com, 2026-09-28):
- the page file has no <html>/<head>/<body> (the platform wraps it); :root is padded by the phone's safe areas,
  so the layout fills 100% (not 100svh) and the in-flow header/bottom sheet do not add the insets again;
- only web types are served (js json txt wasm jpg webp svg ...): .glb .ktx2 .hdr ship as base64 text
  (<name>.b64.txt, +33 %) that nk_artifact_binary.js (published as binary.js) decodes;
- CSP connect-src is 'self' without blob:, so three.js must not fetch() the blob: URLs GLTFLoader makes for the
  model's embedded KTX2 textures (binary.js reads those Blobs directly); 'unsafe-eval' and blob: workers are
  allowed, so the Draco and Basis decoders run as on the LAN site;
- 64 MB per version, 16 MB per text file: one model (the 12 MB KTX2 one) and the 1k panorama for both tiers;
- no query strings (the ?v= keys are dropped) and no Web Share: Share copies ARTIFACT_URL#A-1204 (a plain
  #anchor on the artifact link reaches location.hash).
"""
import base64, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'Website')
OUT = os.path.join(os.path.dirname(HERE), 'Web-Build', 'artifact')
ARTIFACT_URL = 'https://claude.ai/artifact/PvJ7c3P22FwwjifnptQRRH'
SHARE_BASE = sys.argv[1] if len(sys.argv) > 1 else ARTIFACT_URL
LIMIT_TOTAL, LIMIT_TEXT, LIMIT_BINARY = 64e6, 16e6, 15e6

TREES = ['Birch', 'Linden', 'Maple', 'Plane', 'Poplar', 'Shrub']
ASSETS = (['new-komitas-complex-mobile-ktx2.glb', 'komitas-env-1k.hdr', 'komitas-sky.jpg',
           'scene-presentation.json', 'demo-apartments.json', 'tree-instances.json', 'tree/species.json',
           'traffic-routes.json', 'vehicles-lod.glb', 'people.json', 'loading-still.jpg',
           'model-aerial.jpg', 'model-street.jpg', 'model-courtyard.jpg', 'reference-aerial.jpeg',
           'reference-facade.webp', 'plans/demo-1-bed.svg', 'plans/demo-2-bed.svg', 'plans/demo-3-bed.svg']
          + [f'tree/{t}.webp' for t in TREES] + [f'tree/{t}-mobile.webp' for t in TREES]
          + ['lm/' + f for f in sorted(os.listdir(os.path.join(SRC, 'assets/lm'))) if not f.startswith('.')])
VENDOR = sorted(os.path.relpath(os.path.join(d, f), SRC) for d, _, fs in os.walk(os.path.join(SRC, 'vendor'))
                for f in fs if not f.startswith('.'))
JS = ['app.js', 'landscape.js', 'traffic.js', 'traffic-path.js', 'people.js', 'motion-clock.js', 'review-tools.js']
BINARY = ('.glb', '.ktx2', '.hdr')
SERVED = ('.js', '.json', '.txt', '.wasm', '.jpg', '.jpeg', '.webp', '.svg')


def sub(text, old, new):
    """Exact replacement that must hit exactly once (fails loudly when Website/ changed underneath)."""
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'expected 1 x {old[:70]!r}, found {n}')
    return text.replace(old, new)


def js(name):
    text = open(os.path.join(SRC, name), encoding='utf-8').read()
    # Published files are served by path: drop the ?v= cache keys (imports and asset URLs).
    text = re.sub(r'\?v=\d+\.\d+\.\d+', '', text)
    text = text.replace('?v=${RELEASE}', '').replace('?v=${version}', '')
    if name == 'app.js':
        text = sub(text, "import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';\n",
                   "import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';\nimport { fetchBinary, readBlobUrls } from './binary.js';\n")
        text = sub(text, "const $ = (id) => document.getElementById(id);\n",
                   "const $ = (id) => document.getElementById(id);\nreadBlobUrls(THREE);\n")
        # One model for both tiers (the 38 MB JPEG model exceeds the file limit).
        text = sub(text, "const names = mobile ? ['new-komitas-complex-mobile-ktx2.glb', 'new-komitas-complex-mobile.glb']\n"
                         "    : ['new-komitas-complex-mobile-ktx2.glb', 'new-komitas-complex.glb'];",
                   "const names = ['new-komitas-complex-mobile-ktx2.glb'];")
        text = sub(text, "loader.loadAsync(asset(name), progress('Loading the model'))",
                   "loader.parseAsync(await fetchBinary(asset(name), progress('Loading the model')), './assets/')")
        text = sub(text, "if (url.includes('.ktx2')) texture = await ktx2.loadAsync(url);",
                   "if (url.includes('.ktx2')) { const buffer = await fetchBinary(url); texture = await new Promise((resolve, reject) => ktx2.parse(buffer, resolve, reject)); }")
        # One 1k panorama for both tiers (the 2k one does not fit the 64 MB version limit).
        text = sub(text, "const env=await new HDRLoader().loadAsync(asset(mobile&&presentation.environmentMobile||presentation.environment));",
                   "const env=new HDRLoader().createDataTexture(await fetchBinary(asset(presentation.environmentMobile||presentation.environment)));")
        # Share: the frame's own address is not shareable and Web Share is refused, so copy the artifact link.
        start = text.index('async function shareSelected() {')
        end = text.index('\n}\n', start) + 3
        text = text[:start] + (
            "// Claude artifact: links point at the published artifact (a plain #A-1204 reaches the page).\n"
            f"const SHARE_BASE = {json.dumps(SHARE_BASE)};\n"
            "async function shareSelected() {\n"
            "  if (!selected || !SHARE_BASE) return;\n"
            "  const url = `${SHARE_BASE}#${selected.label}`;\n"
            "  try { await navigator.clipboard.writeText(url); toast('Link copied — it opens this apartment.'); return; } catch {}\n"
            "  const field = document.createElement('textarea'); field.value = url; field.setAttribute('readonly', '');\n"
            "  Object.assign(field.style, { position: 'fixed', opacity: '0', top: '0' }); document.body.append(field);\n"
            "  field.select(); field.setSelectionRange(0, url.length);\n"
            "  let copied = false; try { copied = document.execCommand('copy'); } catch {}\n"
            "  field.remove(); toast(copied ? 'Link copied — it opens this apartment.' : url, !copied);\n"
            "}\n") + text[end:]
        text = sub(text, "$('share-detail').addEventListener('click',shareSelected);",
                   "$('share-detail').addEventListener('click',shareSelected);$('share-detail').hidden=!SHARE_BASE;")
        # A link that did not copy stays up long enough to select it.
        text = sub(text, "function toast(text) {\n  clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false;\n"
                         "  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 2700);",
                   "function toast(text, long = false) {\n  clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false;\n"
                   "  toastTimer = setTimeout(() => { $('toast').hidden = true; }, long ? 12000 : 2700);")
    if name == 'traffic.js':
        text = sub(text, "import { sampleLane } from './traffic-path.js';\n",
                   "import { sampleLane } from './traffic-path.js';\nimport { fetchBinary } from './binary.js';\n")
        text = sub(text, "loader.loadAsync(`./assets/vehicles-lod.glb`)",
                   "fetchBinary('./assets/vehicles-lod.glb').then(buffer=>loader.parseAsync(buffer,'./assets/'))")
    # Any loader still fetching a .glb/.ktx2/.hdr by URL would 404 in the artifact.
    left = re.search(r"loadAsync\(asset\(name\)|ktx2\.loadAsync\(|HDRLoader\(\)\.loadAsync\(|loadAsync\(`[^`]*\.glb`\)", text)
    if '?v=' in text or left:
        raise SystemExit(f'{name}: a ?v= key or a direct binary load is left ({left and left.group(0)})')
    return text


ARTIFACT_CSS = """
/* ---- Claude artifact frame ------------------------------------------------------------------------------
   The viewer pads :root by the phone's safe areas, so the page fills 100% of it (not 100svh) and the header
   and bottom sheet do not add the insets a second time. Fixed panels keep their own insets. */
html,body{height:100%}
body{display:flex;flex-direction:column;font:16px/normal 'Avenir Next',Avenir,'Segoe UI',sans-serif;background:#e4eae5;color:var(--ink)}
.topbar{flex:none}
html body main{flex:1 1 auto;height:auto;min-height:0}
@media(max-width:720px){html body .topbar{height:56px;padding-top:0}html body .sidebar{padding-bottom:10px}}
@media(orientation:landscape) and (max-height:520px){html body .sidebar{padding-bottom:8px}}
.toast{-webkit-user-select:text;user-select:text}
"""


def page():
    html = open(os.path.join(SRC, 'index.html'), encoding='utf-8').read()
    css = open(os.path.join(SRC, 'style.css'), encoding='utf-8').read()
    body = html[html.index('<body>') + 6:html.index('</body>')].strip('\n')
    # The brand linked to "./" (a reload); inside the frame that address is not the page's.
    body = sub(body, '<a class="brand" href="./" aria-label="New Komitas demo home">', '<div class="brand">')
    body = sub(body, '<span>New Komitas<small>Photoreal 3D</small></span>\n    </a>',
               '<span>New Komitas<small>Photoreal 3D</small></span>\n    </div>')
    head = ('<title>New Komitas 3D</title>\n'
            '<style>\n' + css.rstrip() + '\n' + ARTIFACT_CSS.strip() + '\n</style>\n'
            '<script type="importmap">{"imports":{"three":"./vendor/three/three.module.js","three/addons/":"./vendor/three/addons/"}}</script>\n'
            '<link rel="modulepreload" href="./vendor/three/three.module.js">\n'
            '<script type="module" src="./app.js"></script>\n')
    out = head + body + '\n'
    if '?v=' in out:
        raise SystemExit('index: a ?v= key is left')
    return out


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    files, sizes64 = [], {}
    for rel in ['assets/' + a for a in ASSETS] + VENDOR:
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel.endswith(BINARY):
            data = base64.b64encode(open(os.path.join(SRC, rel), 'rb').read())
            open(dst + '.b64.txt', 'wb').write(data)
            sizes64[rel] = len(data)
            files.append(rel + '.b64.txt')
        else:
            shutil.copy2(os.path.join(SRC, rel), dst)
            files.append(rel)
    binary_js = open(os.path.join(HERE, 'nk_artifact_binary.js'), encoding='utf-8').read()
    with open(os.path.join(OUT, 'binary.js'), 'w', encoding='utf-8') as f:
        f.write(sub(binary_js, '/*SIZES*/{}', json.dumps(sizes64, indent=1)))
    files.append('binary.js')
    for name in JS:
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(js(name))
        files.append(name)
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page())
    # Local check only (never published): the page inside a copy of the platform's skeleton.
    with open(os.path.join(OUT, '__skeleton.html'), 'w', encoding='utf-8') as f:
        f.write('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
                'body{margin:0;font:14px system-ui,sans-serif;background:#faf9f7}img{max-width:100%}[hidden]{display:none!important}</style>'
                '</head><body>\n' + page() + '</body></html>\n')

    sizes = {rel: os.path.getsize(os.path.join(OUT, rel)) for rel in files}
    total = sum(sizes.values()) + os.path.getsize(os.path.join(OUT, 'index.html'))
    for rel, size in sizes.items():
        if not rel.endswith(SERVED):
            raise SystemExit(f'not a type artifacts serve: {rel}')
        text = rel.endswith(('.js', '.json', '.txt', '.svg'))
        if size > (LIMIT_TEXT if text else LIMIT_BINARY):
            raise SystemExit(f'{rel} is {size / 1e6:.2f} MB, over the per-file limit')
    if total > LIMIT_TOTAL:
        raise SystemExit(f'total {total / 1e6:.2f} MB is over the 64 MB version limit')
    with open(os.path.join(os.path.dirname(OUT), 'artifact-files.json'), 'w') as f:
        json.dump([{'path': rel} for rel in sorted(files)], f, indent=1)
    big = max(sizes, key=sizes.get)
    print(f'{len(files)} files + index.html, {total / 1e6:.2f} MB (limit 64), largest {big} {sizes[big] / 1e6:.2f} MB; '
          f'share links {SHARE_BASE or "off"}')


main()
