import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { Landscape } from './landscape.js?v=0.12.0';
import { Traffic } from './traffic.js?v=0.12.0';
import { People } from './people.js?v=0.12.0';
import { MotionClock } from './motion-clock.js?v=0.12.0';
import { ReviewTools } from './review-tools.js?v=0.12.0';

const $ = (id) => document.getElementById(id);
const RELEASE = '0.12.0';
const asset = name => `./assets/${name}?v=${RELEASE}`;
const statusNames = { available: 'Available', reserved: 'Reserved', sold: 'Sold' };
const statusColors = { available: '#51a978', reserved: '#d5a14a', sold: '#b4736e' };
const storeKey = 'new-komitas-complex-demo-status-v1';
let overrides = {};
try { overrides = JSON.parse(localStorage.getItem(storeKey) || '{}'); } catch {}
let data, units = [], filtered = [], selected = null, renderer, controls, scene, camera;
let model, pickMesh, highlight, landscape, traffic, people, hoverIndex = -1, transition, dirty = true, showAvailability = false;
let listLimit = 30, frameId, toastTimer, lastDraw = 0, review, interacting = false, lastInteraction = 0, readyAt = 0, loadedModel = '';
// The preset view the camera rests on (null once the user takes over), and the aspect it was framed for.
let framed = { view: 'A', aspect: 0 };
const filters = { building: 'all', floor: 'all', bedrooms: 'all', status: 'all' };
const blockerMeshes = [];
const pointer = new THREE.Vector2();
const raycaster = new THREE.Raycaster();
const dummy = new THREE.Object3D();
const params = new URLSearchParams(location.search);
// Asset tier (texture format, trees, reflections, frame budget) is separate from the CSS layout:
// an iPad gets the roomy layout with phone-grade assets. ?mobile / ?desktop force a tier for testing.
const mobile = params.has('mobile') || (!params.has('desktop') && (matchMedia('(pointer: coarse)').matches
  || Math.min(screen.width, screen.height) <= 720 || (navigator.deviceMemory || 8) <= 4));
document.documentElement.classList.toggle('tier-mobile', mobile);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const motion=new MotionClock(reducedMotion.matches);
function updateMotionButton(){
  $('motion-toggle').textContent=motion.paused?'▶':'Ⅱ';
  $('motion-toggle').setAttribute('aria-label',motion.paused?'Play traffic and breeze':'Pause traffic and breeze');
  $('motion-toggle').setAttribute('title',motion.paused?'Play traffic and breeze':'Pause traffic and breeze');
  $('motion-toggle').setAttribute('aria-pressed',String(!motion.paused));
}
$('motion-toggle').addEventListener('click',()=>{motion.setPaused(!motion.paused);updateMotionButton();dirty=true;});
reducedMotion.addEventListener('change',()=>{motion.setPaused(reducedMotion.matches);updateMotionButton();dirty=true;});
document.addEventListener('visibilitychange',()=>{motion.previous=null;});
updateMotionButton();
const host = $('canvas-host');
const defaultView = 'A';
const VIEW_DIRECTION = new THREE.Vector3(-95, 118, 118).normalize();
function courtyardCamera(name = defaultView) {
  const building = data.buildings.find(b => b.id === name);
  if (!building) return null;
  const [x, y] = building.center;
  const target = new THREE.Vector3(x, 22, -y);
  // From the south-west (the sun-lit façades of the baked late-afternoon light), standing back until
  // a ~176 m wide, ~148 m tall frame fits (the block's diagonal plus margin): wide screens keep the
  // original framing, portrait phones step back instead of cropping the block.
  const aspect = camera ? camera.aspect : host.clientWidth / Math.max(1, host.clientHeight);
  const halfV = THREE.MathUtils.degToRad(32) / 2, halfH = Math.atan(Math.tan(halfV) * aspect);
  const distance = Math.max(74 / Math.tan(halfV), 88 / Math.tan(halfH));
  return { position: target.clone().addScaledVector(VIEW_DIRECTION, distance), target };
}
const stateOf = (unit) => statusNames[overrides[unit.id]] ? overrides[unit.id] : unit.status;
const fmt = (n) => n.toLocaleString('en-US', {minimumFractionDigits:1,maximumFractionDigits:1});

for (let floor = 2; floor <= 18; floor++) {
  const option = document.createElement('option'); option.value = floor; option.textContent = `Floor ${floor}`; $('floor-filter').append(option);
}

function toast(text) {
  clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 2700);
}

function matrixFor(unit, scale = 1) {
  dummy.position.fromArray(unit.region.center);
  dummy.rotation.set(0, unit.region.rotationY, 0);
  dummy.scale.set(unit.region.size[0]*scale, unit.region.size[1]*scale, unit.region.size[2]*scale);
  dummy.updateMatrix(); return dummy.matrix;
}

function updateRegions() {
  if (!pickMesh) return;
  const allowed = new Set(filtered.map(u => u.id));
  units.forEach((unit, index) => {
    pickMesh.setMatrixAt(index, matrixFor(unit, allowed.has(unit.id) ? 1 : 0));
    pickMesh.setColorAt(index, new THREE.Color(statusColors[stateOf(unit)]));
  });
  pickMesh.instanceMatrix.needsUpdate = true;
  if (pickMesh.instanceColor) pickMesh.instanceColor.needsUpdate = true;
  pickMesh.computeBoundingSphere(); pickMesh.computeBoundingBox();
  pickMesh.visible = showAvailability;
  if (selected) showHighlight(selected);
  dirty = true;
}

function applyFilters() {
  filtered = units.filter(u => (filters.building === 'all' || u.building === filters.building)
    && (filters.floor === 'all' || u.floor === Number(filters.floor))
    && (filters.bedrooms === 'all' || u.bedrooms === Number(filters.bedrooms))
    && (filters.status === 'all' || stateOf(u) === filters.status));
  listLimit = 30; renderList(); updateRegions();
}

function renderList() {
  $('result-count').textContent = `${filtered.length.toLocaleString()} demo apartments`;
  $('sheet-count').textContent = filtered.length.toLocaleString();
  const fragment = document.createDocumentFragment();
  if (!filtered.length) {
    const p = document.createElement('p'); p.className = 'no-results'; p.textContent = 'No sample apartments match these filters. Reset the filters to explore more homes.'; fragment.append(p);
  }
  for (const unit of filtered.slice(0,listLimit)) {
    const button = document.createElement('button');
    const status = stateOf(unit);
    button.className = `unit-row ${unit.id === selected?.id ? 'selected' : ''}`;
    button.dataset.unit = unit.id;
    button.setAttribute('aria-label', `Demo apartment ${unit.label}, ${unit.bedrooms} ${unit.bedrooms === 1 ? 'bedroom' : 'bedrooms'}, ${fmt(unit.area)} square meters, floor ${unit.floor}, ${statusNames[status]}`);
    button.innerHTML = `<span class="unit-top"><span class="unit-label">${unit.label}</span><span class="unit-status ${status}">${statusNames[status]}</span></span><span class="unit-meta">${unit.bedrooms} ${unit.bedrooms === 1 ? 'bedroom' : 'bedrooms'} · ${fmt(unit.area)} m² · Floor ${unit.floor}</span>`;
    button.addEventListener('click', () => selectUnit(unit)); fragment.append(button);
  }
  if (filtered.length > listLimit) {
    const more = document.createElement('button'); more.className = 'more-results'; more.textContent = 'Show more apartments';
    more.addEventListener('click', () => { const top=$('results').scrollTop,left=$('results').scrollLeft; listLimit += 30; renderList(); $('results').scrollTop=top; $('results').scrollLeft=left; }); fragment.append(more);
  }
  $('results').replaceChildren(fragment);
}


function populateDetail(unit) {
  const status = stateOf(unit);
  $('detail-status').textContent = `${statusNames[status]} · Demo`;
  $('detail-status').className = `status-tag ${status}`;
  $('detail-title').textContent = `Apartment ${unit.label}`;
  $('detail-subtitle').textContent = `Courtyard ${unit.building} · ${unit.courtyardFacing ? 'Courtyard-facing' : 'Outward-facing'}`;
  $('detail-area').textContent = fmt(unit.area); $('detail-beds').textContent = unit.bedrooms; $('detail-floor').textContent = unit.floor;
  const plan=document.createElement('img');plan.src=unit.floorPlan || `./assets/plans/${unit.planType}.svg`;
  plan.alt=`Illustrative ${unit.bedrooms} bedroom floor plan; not an architectural plan`;
  $('floor-plan').replaceChildren(plan);
  document.querySelectorAll('#status-editor button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.status === status)));
}

// Shareable links: #A-1204 opens that apartment; the browser's Back button closes it again.
const unitFromHash = () => { const label = decodeURIComponent(location.hash.slice(1)).trim().toUpperCase(); return label ? units.find(u => u.label.toUpperCase() === label) : null; };
function selectUnit(unit, historyMode = 'push') {
  selected = unit; framed.view = null; populateDetail(unit); $('apartment-detail').hidden = false; $('apartment-detail').scrollTop = 0;
  document.body.classList.add('detail-open');
  if (historyMode !== 'none' && location.hash !== '#' + unit.label) {
    // One history entry for "an apartment is open": switching apartments replaces it.
    if (history.state?.unit) history.replaceState({ ...history.state, unit: unit.id }, '', '#' + unit.label);
    else history.pushState({ unit: unit.id }, '', '#' + unit.label);
  }
  $('hover-card').hidden = true; hoverIndex = -1;
  showHighlight(unit); renderList(); updateViewShift();
  if (camera && controls) {
    const center = new THREE.Vector3().fromArray(unit.region.center);
    const normal = new THREE.Vector3(Math.sin(unit.region.rotationY),0,Math.cos(unit.region.rotationY));
    const probe = new THREE.Raycaster(center.clone().addScaledVector(normal,.25),normal,.1,160);
    const obstacle = probe.intersectObjects(blockerMeshes,false)[0];
    const desiredDistance = unit.courtyardFacing ? 28 : 92;
    const distance = obstacle ? Math.min(desiredDistance,Math.max(8,obstacle.distance-5)) : desiredDistance;
    const destination = center.clone().addScaledVector(normal,distance);
    // Keep the camera in the courtyard or inter-building gap, clear of the opposing roof.
    destination.y = distance < 35 ? Math.max(center.y+28,73) : center.y+31;
    moveCamera(destination,center,1050);
  }
}

function showHighlight(unit) {
  if (!highlight) return;
  highlight.matrix.copy(matrixFor(unit,1.015)); highlight.matrixAutoUpdate = false;
  highlight.material.color.set(statusColors[stateOf(unit)]); highlight.visible = true; dirty = true;
}

function closeDetail(fromHistory = false) {
  selected=null; $('apartment-detail').hidden=true; document.body.classList.remove('detail-open'); if (highlight) highlight.visible=false; renderList(); updateViewShift(); dirty=true;
  if (!fromHistory && location.hash) {
    if (history.state?.unit && !history.state.landing) history.back();
    else history.replaceState(null, '', location.pathname + location.search);
  }
}
window.addEventListener('popstate', () => {
  const unit = unitFromHash();
  if (unit) { if (unit !== selected) selectUnit(unit, 'none'); }
  else if (selected) closeDetail(true);
});

async function shareSelected() {
  if (!selected) return;
  // A clean link: page address + #apartment (no ?qa / ?bench / ?mobile test switches).
  const url = `${location.origin}${location.pathname}#${selected.label}`, title = `New Komitas · Apartment ${selected.label}`;
  const text = `${selected.bedrooms}-bedroom demo apartment, ${fmt(selected.area)} m², floor ${selected.floor}`;
  if (navigator.share) {
    try { await navigator.share({ title, text, url }); return; } catch (error) { if (error.name === 'AbortError') return; }
  }
  if (navigator.clipboard && window.isSecureContext) {
    try { await navigator.clipboard.writeText(url); toast('Link copied — it opens this apartment.'); return; } catch {}
  }
  // Plain http on the local network has no clipboard API: fall back to a selected text copy.
  const field = document.createElement('textarea'); field.value = url; field.setAttribute('readonly', '');
  Object.assign(field.style, { position: 'fixed', opacity: '0', top: '0' }); document.body.append(field);
  field.select(); field.setSelectionRange(0, url.length);
  let copied = false; try { copied = document.execCommand('copy'); } catch {}
  field.remove(); toast(copied ? 'Link copied — it opens this apartment.' : url);
}

// While the detail panel covers part of the stage (a bottom sheet on phones, a side card elsewhere),
// shift the projection so the camera target sits in the middle of the uncovered area.
const viewShift = { x: 0, y: 0, toX: 0, toY: 0 };
function updateViewShift() {
  viewShift.toX = viewShift.toY = 0;
  const panel = $('apartment-detail');
  if (!panel.hidden) {
    const stage = host.getBoundingClientRect(), rect = panel.getBoundingClientRect();
    if (rect.width > stage.width * .75 && rect.top > stage.top + stage.height * .25) viewShift.toY = Math.max(0, stage.bottom - rect.top) / 2;
    else if (rect.left > stage.left + stage.width * .35) viewShift.toX = Math.max(0, stage.right - rect.left + 12) / 2;
  }
  dirty = true;
}
function applyViewShift(dt) {
  if (viewShift.x === viewShift.toX && viewShift.y === viewShift.toY) return false;
  const k = 1 - Math.exp(-dt * 7);
  const nx = viewShift.x + (viewShift.toX - viewShift.x) * k, ny = viewShift.y + (viewShift.toY - viewShift.y) * k;
  viewShift.x = Math.abs(nx - viewShift.toX) < .3 ? viewShift.toX : nx;
  viewShift.y = Math.abs(ny - viewShift.toY) < .3 ? viewShift.toY : ny;
  const w = host.clientWidth, h = host.clientHeight;
  if (viewShift.x || viewShift.y) camera.setViewOffset(w, h, viewShift.x, viewShift.y, w, h); else camera.clearViewOffset();
  return true;
}

// Panning stays inside the modelled neighbourhood.
function clampTarget(v) { v.x = THREE.MathUtils.clamp(v.x, -460, 460); v.z = THREE.MathUtils.clamp(v.z, -460, 460); v.y = THREE.MathUtils.clamp(v.y, 0, 70); return v; }

// Double-click / double-tap: glide halfway towards the building or ground point under the pointer.
function zoomToward(clientX, clientY) {
  if (!camera || !controls) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  let point = raycaster.intersectObjects(blockerMeshes, false)[0]?.point;
  if (!point && raycaster.ray.direction.y < -1e-3) point = raycaster.ray.at(-raycaster.ray.origin.y / raycaster.ray.direction.y, new THREE.Vector3());
  if (!point) return;
  const target = clampTarget(point.clone()), offset = camera.position.clone().sub(controls.target);
  framed.view = null;
  moveCamera(target.clone().add(offset.setLength(Math.max(controls.minDistance + 2, offset.length() * .5))), target, 700);
}

function moveCamera(position, target, duration=1100) {
  if (!camera || !controls) return;
  transition = { start:performance.now(),duration:reducedMotion.matches ? 1 : duration,from:camera.position.clone(),to:position,fromTarget:controls.target.clone(),toTarget:target };
  dirty=true;
}

function view(name) {
  const preset = courtyardCamera(name);
  if (!preset) return;
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active',b.dataset.view===name));
  $('hover-card').hidden=true;
  framed = { view: name, aspect: camera.aspect };
  moveCamera(preset.position, preset.target);
}

// Adaptive resolution: if frames arrive much later than the frame budget allows (GPU-bound),
// render fewer pixels; recover slowly once there is headroom again.
const quality = { scale: 1, min: mobile ? .6 : .8, sum: 0, count: 0, changed: 0, vsync: 16.7, lastTick: 0 };
function frameBudget(now) {
  // Phones: full rate while the camera moves, ~25 fps for traffic and breeze alone (battery, heat).
  const active = interacting || transition || review?.active || now - lastInteraction < 700;
  return mobile ? (active ? 15 : 38) : 12;
}
function adaptResolution(interval, budget, now) {
  if (interval > 250) { quality.sum = quality.count = 0; return; }        // idle gap, not a measurement
  const expected = Math.max(1, Math.ceil((budget - 1) / quality.vsync)) * quality.vsync;
  quality.sum += interval / expected; quality.count++;
  if (quality.count < 40) return;
  const load = quality.sum / quality.count; quality.sum = quality.count = 0;
  if (load > 1.4 && quality.scale > quality.min) { quality.scale = Math.max(quality.min, quality.scale * .85); quality.changed = now; resize(); }
  else if (load < 1.1 && quality.scale < 1 && now - quality.changed > 4000) { quality.scale = Math.min(1, quality.scale / .85); quality.changed = now; resize(); }
}

const drawSize = new THREE.Vector2();
function resize() {
  if (!renderer) return;
  const width=host.clientWidth,height=host.clientHeight;
  if (!width || !height) return;
  const pixelBudget=mobile?1_500_000:3_000_000;
  const ratio=Math.max(.5,Math.min(window.devicePixelRatio||1,mobile?1.6:2,Math.sqrt(pixelBudget/(width*height)))*quality.scale);
  // Resizing the canvas wipes it: only touch it when something changed, then draw at once so a
  // blank (black) frame is never shown (this flashed while phones adapted their resolution).
  renderer.getSize(drawSize);
  const changed = Math.abs(renderer.getPixelRatio() - ratio) > 1e-3 || drawSize.x !== width || drawSize.y !== height;
  if (changed) { renderer.setPixelRatio(ratio); renderer.setSize(width,height,false); }
  camera.aspect=width/height;
  if (viewShift.x || viewShift.y) camera.setViewOffset(width, height, viewShift.x, viewShift.y, width, height);
  camera.updateProjectionMatrix();
  if (changed && scene && controls) { renderer.render(scene, camera); lastDraw = performance.now(); }
  if (controls) controls.maxDistance = camera.aspect < .8 ? 680 : 490;
  updateViewShift(); dirty=true;
  // Sheet folded, phone rotated: re-frame a preset view the user has not moved away from.
  if (framed.view && data && !selected) {
    if (!framed.aspect) framed.aspect = camera.aspect;
    else if (Math.abs(camera.aspect / framed.aspect - 1) > .08) view(framed.view);
  }
}

function createOccluders() {
  // Six solid wing boxes per block (the model's own roof rectangles) stand in for the façade
  // detail: picking must not raycast hundreds of thousands of balcony triangles.
  for(const b of data.buildings){
    const height=b.height||(b.groundHeight+b.residentialFloors*b.floorHeight);
    for(const [x0,y0,x1,y1] of b.rects){
      const mesh=new THREE.Mesh(new THREE.BoxGeometry(x1-x0,height,y1-y0));
      mesh.position.set((x0+x1)/2,height/2,-(y0+y1)/2);
      mesh.visible=false;mesh.name='Selection occluder '+b.id;scene.add(mesh);blockerMeshes.push(mesh);
    }
  }
  scene.updateMatrixWorld(true);
}

/** Raycast-only views of a large static mesh: ~48 m ground tiles sharing its vertex buffer, each with
 *  its own bounds, so a pick ray tests a few thousand triangles instead of ~180k. */
function raycastTiles(mesh, cell = 48) {
  const geometry = mesh.geometry, position = geometry.attributes.position, index = geometry.index?.array;
  if (!index || position.isInterleavedBufferAttribute) return [mesh];
  const p = position.array, tris = index.length / 3, keys = new Int32Array(tris), counts = new Map();
  for (let t = 0; t < tris; t++) {
    const a = 3 * index[3 * t], b = 3 * index[3 * t + 1], c = 3 * index[3 * t + 2];
    const key = (Math.floor((p[a] + p[b] + p[c]) / (3 * cell)) + 512) * 1024 + Math.floor((p[a + 2] + p[b + 2] + p[c + 2]) / (3 * cell)) + 512;
    keys[t] = key; counts.set(key, (counts.get(key) || 0) + 1);
  }
  const tiles = new Map();
  for (const [key, n] of counts) tiles.set(key, { index: new Uint32Array(n * 3), n: 0, box: new THREE.Box3() });
  const v = new THREE.Vector3();
  for (let t = 0; t < tris; t++) {
    const tile = tiles.get(keys[t]);
    for (let k = 0; k < 3; k++) { const i = index[3 * t + k]; tile.index[tile.n++] = i; tile.box.expandByPoint(v.set(p[3 * i], p[3 * i + 1], p[3 * i + 2])); }
  }
  mesh.updateWorldMatrix(true, false);
  return [...tiles.values()].map(tile => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', position); g.setIndex(new THREE.BufferAttribute(tile.index, 1));
    g.boundingBox = tile.box; g.boundingSphere = tile.box.getBoundingSphere(new THREE.Sphere());
    const m = new THREE.Mesh(g, mesh.material); m.name = mesh.name + ' raycast tile'; m.visible = false;
    m.matrixAutoUpdate = false; m.matrix.copy(mesh.matrixWorld); m.matrixWorld.copy(mesh.matrixWorld);
    return m;
  });
}

function pickAt(clientX, clientY) {
  const rect=renderer.domElement.getBoundingClientRect();
  pointer.set((clientX-rect.left)/rect.width*2-1,-(clientY-rect.top)/rect.height*2+1);
  raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObject(pickMesh,false);
  if (!hits.length)return null;
  const hit=hits[0];
  const blockers=raycaster.intersectObjects(blockerMeshes,false);
  if(blockers.length && blockers[0].distance<hit.distance-.6) return null;
  return { unit:units[hit.instanceId],index:hit.instanceId };
}
// Fingers cover ~40 px: a tap also tries a ring of nearby points (the exact point wins).
const TAP_RING = [[0,0],[1,0],[-1,0],[0,1],[0,-1],[.7,.7],[-.7,.7],[.7,-.7],[-.7,-.7]];
function hitTest(event, radius = 0) {
  if (!pickMesh || !renderer || transition) return null;
  for (const [dx, dy] of radius ? TAP_RING : TAP_RING.slice(0, 1)) {
    const hit = pickAt(event.clientX + dx * radius, event.clientY + dy * radius);
    if (hit) return hit;
  }
  return null;
}

function animate(now) {
  frameId=requestAnimationFrame(animate);
  frame(now);
}

function frame(now, force = false) {
  if (quality.lastTick) quality.vsync = Math.min(now - quality.lastTick, quality.vsync + .01);
  const dt = Math.min(.1, (now - (quality.lastTick || now)) / 1000); quality.lastTick = now;
  const hidden = document.hidden && !force;
  if(motion.tick(now,hidden,review?.checking))dirty=true;
  // The QA pixel comparison owns rendering until it restores the camera.
  // Otherwise a throttled compact frame can update wind between comparisons.
  if(hidden||review?.checking)return;
  if(transition){
    const t=Math.min(1,(now-transition.start)/transition.duration); const ease=1-Math.pow(1-t,3);
    camera.position.lerpVectors(transition.from,transition.to,ease); controls.target.lerpVectors(transition.fromTarget,transition.toTarget,ease); dirty=true;
    if(t===1){transition=null;lastInteraction=now;}
  }
  if(applyViewShift(dt))dirty=true;
  if(review?.beforeFrame(now))dirty=true;
  if(controls.update())dirty=true;
  const near=Math.max(1.5,Math.min(6,camera.position.distanceTo(controls.target)*.012));
  if(Math.abs(camera.near-near)>.01){camera.near=near;camera.updateProjectionMatrix();}
  if(landscape?.update(camera))dirty=true;
  const budget=frameBudget(now);
  if(dirty && now-lastDraw>budget) {
    traffic?.update(motion.time,camera);people?.update(motion.time);landscape?.animate(motion.time);
    renderer.render(scene,camera);review?.afterRender(now);dirty=false;
    adaptResolution(now-lastDraw,budget,now);lastDraw=now;
  }
}

function progress(label) {
  return event => {
    if (!event.total) return;
    $('loading-bar').style.width = `${Math.round(event.loaded / event.total * 70)}%`;
    $('loading-message').textContent = event.loaded >= event.total ? 'Unpacking geometry and textures…'
      : `${label} · ${Math.round(event.loaded / event.total * 100)}% of ${(event.total / 1e6).toFixed(0)} MB`;
  };
}

async function loadModel(loader) {
  // GPU-compressed KTX2 textures first (8x less GPU memory). Desktops open with this 12 MB model and
  // then stream 4096 px lightmaps (upgradeTextures); the JPEG models are the fallbacks.
  const names = mobile ? ['new-komitas-complex-mobile-ktx2.glb', 'new-komitas-complex-mobile.glb']
    : ['new-komitas-complex-mobile-ktx2.glb', 'new-komitas-complex.glb'];
  for (const [i, name] of names.entries()) {
    try { const gltf = await loader.loadAsync(asset(name), progress('Loading the model')); loadedModel = name; return gltf; }
    catch (error) { if (i === names.length - 1) throw error; console.warn(`Could not load ${name}; trying the next variant`, error); }
  }
}

// Desktop: replace the 2048 px lightmaps with full-resolution ones (assets/lm/manifest.json: KTX2 for the
// neighbours and ground, the original JPEGs for the two blocks), the most looked-at surfaces first.
async function upgradeTextures(ktx2) {
  let manifest;
  try { manifest = (await (await fetch(asset('lm/manifest.json'))).json()).textures; }
  catch { ktx2.dispose(); return; }
  const groups = new Map();
  model.traverse(o => { if (!o.isMesh || !o.visible) return; for (const m of [].concat(o.material)) {
    const name = m.map?.name?.replace(/_half$/, ''); if (manifest[name]) { if (!groups.has(name)) groups.set(name, []); groups.get(name).push(m); } } });
  const rank = n => ['A_Shell', 'B_Shell', 'A_Balconies', 'B_Balconies', 'ContextNearW', 'ContextNearE', 'Ground', 'ContextFar'].findIndex(k => n.includes(k)) >>> 0;
  const names = [...groups.keys()].sort((a, b) => rank(a) - rank(b));
  // JPEGs decode off the main thread where createImageBitmap is reliable (not Safari).
  const bitmaps = typeof createImageBitmap !== 'undefined' && !/^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  const images = bitmaps ? new THREE.ImageBitmapLoader().setOptions({ imageOrientation: 'none', premultiplyAlpha: 'none' }) : new THREE.TextureLoader();
  const chip = document.createElement('span'); chip.className = 'sharpen-chip'; chip.setAttribute('role', 'status'); document.querySelector('.stage').append(chip);
  for (const [i, name] of names.entries()) {
    chip.textContent = `Sharpening textures · ${i + 1}/${names.length}`;
    try {
      const url = asset('lm/' + manifest[name]);
      let texture;
      if (url.includes('.ktx2')) texture = await ktx2.loadAsync(url);
      else if (bitmaps) { texture = new THREE.Texture(await images.loadAsync(url)); texture.onUpdate = () => texture.image.close?.(); }
      else texture = await images.loadAsync(url);
      const materials = groups.get(name), old = materials[0].map;
      texture.flipY = false; texture.colorSpace = THREE.SRGBColorSpace; texture.wrapS = old.wrapS; texture.wrapT = old.wrapT;
      texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); texture.name = name;
      if (!texture.isCompressedTexture) texture.needsUpdate = true;
      for (const m of materials) { m.map = texture; m.needsUpdate = true; }
      old.dispose(); dirty = true;
    } catch (error) { console.warn('Keeping the 2048 px lightmap for', name, error); }
  }
  chip.remove(); ktx2.dispose();
}

function hideLoading() {
  const el = $('loading'); $('loading-bar').style.width = '100%';
  el.classList.add('done'); setTimeout(() => { if (el.classList.contains('done')) el.hidden = true; }, 800);
}

async function startScene() {
  const presentationResponse=await fetch(asset('scene-presentation.json'));
  if(!presentationResponse.ok)throw new Error('Scene lighting could not be loaded.');
  const presentation=await presentationResponse.json(),lighting=presentation.lighting;
  scene=new THREE.Scene(); scene.background=new THREE.Color(presentation.horizon);scene.fog=new THREE.Fog(presentation.horizon,presentation.fog[0],presentation.fog[1]);
  const initialView = courtyardCamera(defaultView);
  camera=new THREE.PerspectiveCamera(32,1,4,4000);camera.position.copy(initialView.position);
  const canvas=document.createElement('canvas');
  // ?qa keeps the drawing buffer so screenshots of a hidden preview pane show the last frame.
  const keep=params.has('qa');
  const context=canvas.getContext('webgl2',{antialias:true,alpha:false,powerPreference:'high-performance',preserveDrawingBuffer:keep});
  if(!context)throw new Error('WebGL 2 is unavailable on this device.');
  // ?stddepth simulates browsers without EXT_clip_control (iPhone Safari): a standard depth buffer.
  renderer=new THREE.WebGLRenderer({canvas,context,antialias:true,alpha:false,preserveDrawingBuffer:keep,reversedDepthBuffer:!params.has('stddepth')&&!!context.getExtension('EXT_clip_control')});
  // Baked surfaces are already display-referred (Blender AgX); live materials (glass, cars) use three's AgX too.
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=lighting.exposure;
  renderer.shadowMap.enabled=false;
  renderer.domElement.setAttribute('aria-label','New Komitas complex. Drag to rotate, pinch or scroll to zoom. Apartments are also available in the list.');
  renderer.domElement.setAttribute('role','img');
  host.append(renderer.domElement);
  // Reflections: a Cycles panorama of the real surroundings under the baked sun (our blocks hidden).
  $('loading-message').textContent='Loading the sky and reflections…';
  const env=await new HDRLoader().loadAsync(asset(mobile&&presentation.environmentMobile||presentation.environment));
  env.mapping=THREE.EquirectangularReflectionMapping;
  const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromEquirectangular(env).texture;
  scene.environmentIntensity=lighting.skyStrength;env.dispose();pmrem.dispose();
  // Background: the same Cycles sky (sun disc and haze), shown through the display transform of the bake.
  const skyTex=await new THREE.TextureLoader().loadAsync(asset(presentation.sky));
  skyTex.mapping=THREE.EquirectangularReflectionMapping;skyTex.colorSpace=THREE.SRGBColorSpace;
  scene.background=skyTex;scene.backgroundIntensity=1;
  controls=new OrbitControls(camera,renderer.domElement);controls.target.copy(initialView.target);
  // Right-drag / two fingers move along the ground (kept inside the neighbourhood by clampTarget).
  controls.enableDamping=true;controls.dampingFactor=.075;controls.enablePan=true;controls.screenSpacePanning=false;controls.panSpeed=.8;
  controls.minDistance=34;controls.maxDistance=490;
  controls.maxPolarAngle=Math.PI*.46;controls.minPolarAngle=.12;controls.rotateSpeed=mobile?.8:.6;controls.zoomSpeed=.85;
  controls.addEventListener('start',()=>{transition=null;interacting=true;framed.view=null;$('hover-card').hidden=true;});
  controls.addEventListener('end',()=>{interacting=false;lastInteraction=performance.now();});
  const clampShift=new THREE.Vector3();
  controls.addEventListener('change',()=>{clampShift.copy(controls.target);clampTarget(controls.target);clampShift.subVectors(controls.target,clampShift);if(clampShift.lengthSq())camera.position.add(clampShift);dirty=true;});
  scene.add(new THREE.HemisphereLight('#dcecf5','#7d7358',lighting.hemisphere??lighting.skyStrength*.42));
  // Match the native sun: Blender (x,y,z) becomes Three.js (x,z,-y).
  const sun=new THREE.DirectionalLight(new THREE.Color(...lighting.sunColor),lighting.sunEnergy);
  const [sx,sy,sz]=lighting.sunDirection;sun.position.set(-sx,-sz,sy);scene.add(sun);
  const loader=new GLTFLoader();
  const draco=new DRACOLoader().setDecoderPath('./vendor/draco/').setWorkerLimit(mobile?2:4);
  loader.setDRACOLoader(draco);
  const ktx2=new KTX2Loader().setTranscoderPath('./vendor/three/addons/libs/basis/').setWorkerLimit(2).detectSupport(renderer);
  loader.setKTX2Loader(ktx2);
  const gltf=await loadModel(loader);
  const sharpen=!mobile&&loadedModel.includes('ktx2');
  if(!sharpen)ktx2.dispose();
  model=gltf.scene;
  model.traverse(obj=>{if(obj.isMesh){
    // The static aggregate contains the old fleet. Its ground shadows have been
    // rebaked out; replace body, windows and hardware together with live instances.
    if(obj.name.startsWith('Vehicles__')||obj.name==='Baked_vehicles'){obj.visible=false;return;}
    const materials=Array.isArray(obj.material)?obj.material:[obj.material];
    const replacements=materials.map(material=>{
      if(material.map)material.map.anisotropy=Math.min(mobile?4:8,renderer.capabilities.getMaxAnisotropy());
      // Glass reflects the real surroundings' panorama; at ~10% Fresnel it read as black holes from
      // most angles, so give the reflections the strength of a sunny day's sky.
      if(/^Glass_(Window|Shop|Curtain|Spandrel)/.test(material.name))material.envMapIntensity=1.7;
      if(material.name.startsWith('Baked_')){
        // Ground tiles meet edge to edge: a repeating sampler blended each tile's border with the opposite
        // border and drew a thin line across the site (and through both courtyards at y = 0).
        if(/^Baked_(Ground_|site)/.test(material.name)&&material.map){material.map.wrapS=material.map.wrapT=THREE.ClampToEdgeWrapping;material.map.needsUpdate=true;}
        const baked=new THREE.MeshBasicMaterial({map:material.map,toneMapped:false});
        if(material.name==='Baked_site'){
          // Extend the terrain into haze without stretching the last texel row
          // into long stripes beyond the finite lighting atlas.
          const edge=new THREE.Color(presentation.terrainEdge);
          baked.onBeforeCompile=shader=>{
            shader.uniforms.terrainEdge={value:edge};
            shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nuniform vec3 terrainEdge;')
              .replace('#include <map_fragment>','#include <map_fragment>\nfloat edgeFade=1.-smoothstep(.42,.50,max(abs(vMapUv.x-.5),abs(vMapUv.y-.5)));\ndiffuseColor.rgb=mix(terrainEdge,diffuseColor.rgb,edgeFade);');
          };
          baked.customProgramCacheKey=()=> 'terrain-edge-v1';
        }
        return baked;
      }
      return material;
    });
    obj.material=Array.isArray(obj.material)?replacements:replacements[0];
    obj.castShadow=false;obj.receiveShadow=false;
  }});
  scene.add(model);createOccluders();
  // Real neighbours block fly-to cameras and picks like our own wings do (through raycast tiles).
  model.traverse(obj=>{if(obj.isMesh&&/Context/.test(obj.name))blockerMeshes.push(...raycastTiles(obj));});
  scene.updateMatrixWorld(true);
  $('loading-message').textContent='Adding the surrounding landscape…';$('loading-bar').style.width='80%';
  landscape=await Landscape.load(scene,loader,mobile,RELEASE);
  $('loading-message').textContent='Bringing the neighborhood to life…';$('loading-bar').style.width='92%';
  traffic=await Traffic.load(scene,loader,RELEASE,mobile);traffic.setSun(sun.position);
  // People are optional: the scene works without assets/people.json.
  people=await People.load(scene,RELEASE,mobile).catch(error=>{console.warn('No people:',error);return null;});people?.setSun(sun.position);
  draco.dispose();
  pickMesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.28,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}),units.length);
  pickMesh.name='Demo apartment selectable regions';pickMesh.renderOrder=2;scene.add(pickMesh);
  highlight=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshBasicMaterial({color:'#51a978',transparent:true,opacity:.6,depthWrite:false}));
  highlight.visible=false;highlight.renderOrder=3;scene.add(highlight);updateRegions();
  let down=null,lastTap=null,pendingTap=0,lastPointer='mouse';
  renderer.domElement.addEventListener('pointerdown',event=>{down={x:event.clientX,y:event.clientY};lastPointer=event.pointerType;});
  renderer.domElement.addEventListener('pointerup',event=>{
    if(!down)return;const moved=Math.hypot(event.clientX-down.x,event.clientY-down.y),touch=event.pointerType!=='mouse';down=null;
    if(moved>=(touch?10:6))return;
    if(!touch){const hit=hitTest(event);if(hit)selectUnit(hit.unit);return;}
    // Touch, maps-style: a second tap within 280 ms zooms; otherwise (after the same 280 ms) the tap selects.
    const now=performance.now(),tap={x:event.clientX,y:event.clientY,t:now};
    if(lastTap&&now-lastTap.t<280&&Math.hypot(tap.x-lastTap.x,tap.y-lastTap.y)<32){clearTimeout(pendingTap);lastTap=null;zoomToward(tap.x,tap.y);return;}
    lastTap=tap;clearTimeout(pendingTap);
    pendingTap=setTimeout(()=>{const hit=hitTest({clientX:tap.x,clientY:tap.y},14);if(hit)selectUnit(hit.unit);},280);
  });
  renderer.domElement.addEventListener('dblclick',event=>{if(lastPointer==='mouse')zoomToward(event.clientX,event.clientY);});
  renderer.domElement.addEventListener('pointercancel',()=>{down=null;});
  let lastMove=0;
  renderer.domElement.addEventListener('pointermove',event=>{
    if(event.pointerType==='touch'||down||performance.now()-lastMove<75)return;lastMove=performance.now();
    const hit=hitTest(event);
    renderer.domElement.style.cursor=hit?'pointer':'grab';
    if(hit){
      if(hoverIndex!==hit.index){hoverIndex=hit.index;if(!selected)showHighlight(hit.unit);const st=stateOf(hit.unit);$('hover-card').innerHTML=`<strong>${hit.unit.label}</strong>${hit.unit.bedrooms} ${hit.unit.bedrooms === 1 ? 'bedroom' : 'bedrooms'} · ${fmt(hit.unit.area)} m²<span class="unit-status ${st}">${statusNames[st]} · Demo</span>`;}
      const rect=host.getBoundingClientRect();$('hover-card').style.left=`${Math.min(event.clientX-rect.left+16,rect.width-175)}px`;$('hover-card').style.top=`${Math.max(10,event.clientY-rect.top-95)}px`;$('hover-card').hidden=false;
    }else{hoverIndex=-1;$('hover-card').hidden=true;if(!selected)highlight.visible=false;dirty=true;}
  });
  renderer.domElement.addEventListener('pointerleave',()=>{$('hover-card').hidden=true;hoverIndex=-1;if(!selected){highlight.visible=false;dirty=true;}});
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frameId);showError('The 3D view was interrupted (the phone may have reclaimed its memory). Reload it to continue exploring.');});
  new ResizeObserver(resize).observe(host);resize();controls.update();
  hideLoading();readyAt=performance.now();
  // Some browsers settle the canvas size a frame late: redraw a couple of times after load.
  for(const ms of [120,500,1500])setTimeout(()=>{resize();dirty=true;},ms);
  if(filters.building!=='all')view(filters.building);
  const linked=unitFromHash();
  if(linked){history.replaceState({unit:linked.id,landing:true},'',location.href);selectUnit(linked,'none');}
  if(sharpen)setTimeout(()=>upgradeTextures(ktx2),400);
  if(params.has('qa')||params.has('bench')){
    review=new ReviewTools(renderer,scene,camera,controls,mobile,()=>{dirty=true;},()=>landscape.update(camera),RELEASE,
      ()=>({time:motion.time,paused:motion.paused,windTime:landscape.windTime.value,...traffic.diagnostics(),hiddenStaticCars:window.komitasQA.modelNames().filter(o=>o.name.includes('vehicles')||o.name.startsWith('Vehicles__'))}),landscape);
    review.results.motion={movingCars:traffic.diagnostics().moving,vehicleModels:2,trees:landscape.rows.length};
    // Read-only diagnostics for local motion/placement/performance verification.
    window.komitasQA={traffic:()=>traffic.diagnostics(),motion:()=>({time:motion.time,paused:motion.paused,windTime:landscape.windTime.value}),
      tier:()=>({mobile,pixelRatio:renderer.getPixelRatio(),quality:quality.scale,vsync:quality.vsync}),
      // Hidden preview panes pause requestAnimationFrame: step the frame loop by hand (60 fps clock).
      advance:(seconds=1)=>{let t=performance.now();for(let i=0;i<Math.ceil(seconds*60);i++){t+=1000/60;dirty=dirty||i%2===0;frame(t,true);}lastDraw=0;quality.lastTick=0;motion.previous=null;return renderer.info.render.frame;},
      internals:()=>({THREE,landscape,traffic,people,renderer,scene,camera,controls,blockerMeshes,hitTest}),
      people:()=>people?.diagnostics(),
      modelNames:()=>{const names=[];model.traverse(o=>{if(o.isMesh)names.push({name:o.name,visible:o.visible});});return names;}};
  }
  if(params.has('bench'))runBenchmark();
  requestAnimationFrame(animate);
  console.info(`New Komitas demo ready (${mobile?'mobile':'desktop'} assets): ${units.length} synthetic apartments. Approximate exterior; no live inventory.`);
}

// ?bench: a 16 s orbit measured on this device; the result is shown and saved on the Mac (serve.py).
function gpuName(){const gl=renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);}
function runBenchmark(){
  const card=$('bench-card');review.panel.hidden=true;
  card.hidden=false;card.innerHTML='<strong>Measuring this device…</strong>The camera circles the complex for about 16 seconds. Keep the screen on and don\'t touch it.';
  let compressed=false;model.traverse(o=>{if(o.isMesh&&o.material?.map?.isCompressedTexture)compressed=true;});
  review.onOrbitDone=async results=>{
    const o=results.orbit,report={...results,release:RELEASE,tier:mobile?'mobile':'desktop',model:loadedModel,compressedTextures:compressed,
      readyMs:Math.round(readyAt),pixelRatio:+renderer.getPixelRatio().toFixed(2),adaptiveScale:+quality.scale.toFixed(2),devicePixelRatio,
      screen:[screen.width,screen.height],viewport:[innerWidth,innerHeight],gpu:gpuName(),deviceMemory:navigator.deviceMemory||null,
      jsHeapMB:performance.memory?Math.round(performance.memory.usedJSHeapSize/1e6):null,page:location.pathname+location.search};
    let saved=false;try{saved=(await fetch('/__report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report)})).ok;}catch{}
    card.innerHTML=`<strong>${o.medianFps} fps (median)</strong>slowest 5% of frames: ${o.p95FrameMs} ms · ready after ${(report.readyMs/1000).toFixed(1)} s<br>${report.gpu}<small>${saved?'Saved on the Mac in Web-Build/device-reports.':'The Mac could not be reached, so the result is only shown here.'}</small><button id="bench-close">Close</button>`;
    $('bench-close').onclick=()=>{card.hidden=true;};
  };
  setTimeout(()=>review.startOrbit(false),1500);
}

function showError(message){$('loading').classList.remove('done');$('loading').hidden=false;$('loading').classList.add('error');$('loading').querySelector('strong').textContent='The 3D view could not load';$('loading-message').textContent=message;$('retry').hidden=false;}

// Narrow screens: short first options so the three filters fit side by side at a 16 px font.
const narrowQuery=matchMedia('(max-width: 720px)');
function filterLabels(){const n=narrowQuery.matches;$('floor-filter').options[0].textContent=n?'All':'All floors';$('status-filter').options[0].textContent=n?'All':'All sample statuses';}
narrowQuery.addEventListener('change',filterLabels);filterLabels();

// Phones (portrait): the apartment list is a bottom sheet that folds down to its header.
const sheetToggle=$('sheet-toggle');
function setSheet(open){document.body.classList.toggle('sheet-collapsed',!open);sheetToggle.setAttribute('aria-expanded',String(open));}
sheetToggle.addEventListener('click',()=>setSheet(document.body.classList.contains('sheet-collapsed')));
if(matchMedia('(max-width: 720px) and (max-height: 720px)').matches)setSheet(false);

document.querySelectorAll('[data-building]').forEach(button=>button.addEventListener('click',()=>{filters.building=button.dataset.building;document.querySelectorAll('[data-building]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));applyFilters();if(camera)view(filters.building==='all'?defaultView:filters.building);}));
for(const [id,key]of[['floor-filter','floor'],['bed-filter','bedrooms'],['status-filter','status']])$(id).addEventListener('change',e=>{filters[key]=e.target.value;applyFilters();});
$('clear-filters').addEventListener('click',()=>{Object.keys(filters).forEach(k=>filters[k]='all');for(const id of['floor-filter','bed-filter','status-filter'])$(id).value='all';document.querySelectorAll('[data-building]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.building==='all')));applyFilters();});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>view(b.dataset.view)));
$('reset-camera').addEventListener('click',()=>view(defaultView));
$('zoom-in').addEventListener('click',()=>{if(!camera)return;const offset=camera.position.clone().sub(controls.target).multiplyScalar(.8);moveCamera(controls.target.clone().add(offset),controls.target.clone(),400);});
$('zoom-out').addEventListener('click',()=>{if(!camera)return;const offset=camera.position.clone().sub(controls.target).multiplyScalar(1.25);moveCamera(controls.target.clone().add(offset),controls.target.clone(),400);});
$('availability-toggle').addEventListener('click',()=>{showAvailability=!showAvailability;$('availability-toggle').setAttribute('aria-pressed',String(showAvailability));if(pickMesh)pickMesh.visible=showAvailability;dirty=true;});
$('close-detail').addEventListener('click',()=>closeDetail());
$('share-detail').addEventListener('click',shareSelected);
document.querySelectorAll('#status-editor button').forEach(button=>button.addEventListener('click',()=>{if(!selected)return;overrides[selected.id]=button.dataset.status;try{localStorage.setItem(storeKey,JSON.stringify(overrides));}catch{}populateDetail(selected);applyFilters();toast(`Demo ${selected.label} is now ${statusNames[button.dataset.status].toLowerCase()}.`);}));
$('reset-inventory').addEventListener('click',()=>{overrides={};try{localStorage.removeItem(storeKey);}catch{}if(selected)populateDetail(selected);applyFilters();toast('All sample statuses restored.');});
$('reference-button').addEventListener('click',()=>$('reference-dialog').showModal());
$('notes-button').addEventListener('click',()=>$('notes-dialog').showModal());
document.querySelectorAll('.close-dialog').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
const referenceImages={
  'aerial':['./assets/reference-aerial.jpeg','Developer aerial rendering of the two New Komitas courtyard blocks'],
  'facade':['./assets/reference-facade.webp','Developer façade rendering showing pale walls and bronze framing'],
  'model-aerial':['./assets/model-aerial.jpg','Photoreal Cycles still of the new model among the real neighbouring buildings'],
  'model-street':['./assets/model-street.jpg','Photoreal Cycles still of the west façade from the street between the neighbouring towers'],
  'model-courtyard':['./assets/model-courtyard.jpg','Photoreal Cycles still inside Courtyard A'],
};
document.querySelectorAll('[data-reference]').forEach(b=>b.addEventListener('click',()=>{const [src,alt]=referenceImages[b.dataset.reference];$('reference-image').src=src;$('reference-image').alt=alt;document.querySelectorAll('[data-reference]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn===b)));b.scrollIntoView({block:'nearest',inline:'nearest'});}));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&selected&&!$('reference-dialog').open&&!$('notes-dialog').open)closeDetail();});
$('retry').addEventListener('click',()=>location.reload());

try{
  const response=await fetch(asset('demo-apartments.json'));if(!response.ok)throw new Error('Apartment data could not be read.');
  data=await response.json();units=data.apartments;applyFilters();
  try{await startScene();}catch(error){console.error(error);showError('The apartment list is available. Try reloading the 3D view or use a browser with WebGL support.');}
}catch(error){console.error(error);$('result-count').textContent='Demo data unavailable';showError('The demo files could not be loaded. Start the local server from this project folder and try again.');}
