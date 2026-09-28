import * as THREE from 'three';

/** People on the pavements, paths, plaza and courtyards (assets/people.json, made in Blender by nk_people.py).
 *  Four procedurally modelled body types (~900 triangles each) drawn as GPU instances; clothes, skin and hair
 *  colours per person; the walk / run / stand / sit poses are computed in the vertex shader (joint rotations at
 *  hip, knee, shoulder, elbow). Sun visibility along every route is precomputed against the baked scene, so
 *  a person in shade loses the direct sun but keeps the sky light, and casts a soft sun shadow only in the sun. */

const GROUND = .222;                       // the baked ground tiles lie 0.22 m above the model's zero
const SEG = {BODY: 0, L_THIGH: 1, L_SHIN: 2, R_THIGH: 3, R_SHIN: 4, L_UPPER: 5, L_FORE: 6, R_UPPER: 7, R_FORE: 8};
const REG = {SKIN: 0, HAIR: 1, TOP: 2, BOTTOM: 3, SHOES: 4, BAG: 5};

function mulberry32(a) {
  return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

class FigureBuilder {
  constructor(n) { this.n = n; this.pos = []; this.seg = []; this.reg = []; this.idx = []; }
  vert(x, y, z, seg, reg) { this.pos.push(x, y, z); this.seg.push(seg); this.reg.push(reg); return this.pos.length / 3 - 1; }
  /** Closed tube through elliptic rings [y, rx, rz, cx, cz] (ascending y), with end caps. */
  tube(rings, seg, reg, n = this.n) {
    const base = this.pos.length / 3;
    for (const [y, rx, rz, cx = 0, cz = 0] of rings) for (let k = 0; k < n; k++) {
      const a = 2 * Math.PI * k / n; this.vert(cx + rx * Math.cos(a), y, cz + rz * Math.sin(a), seg, reg);
    }
    for (let r = 0; r < rings.length - 1; r++) for (let k = 0; k < n; k++) {
      const a = base + r * n + k, b = base + r * n + (k + 1) % n, c = a + n, d = b + n; this.idx.push(a, c, b, b, c, d);
    }
    const [y0, , , x0 = 0, z0 = 0] = rings[0], [y1, , , x1 = 0, z1 = 0] = rings[rings.length - 1];
    const bot = this.vert(x0, y0, z0, seg, reg), top = this.vert(x1, y1, z1, seg, reg), last = base + (rings.length - 1) * n;
    for (let k = 0; k < n; k++) { this.idx.push(bot, base + k, base + (k + 1) % n); this.idx.push(top, last + (k + 1) % n, last + k); }
  }
  /** Ellipsoid (or a band of it between two latitudes, in degrees). */
  ellipsoid(cx, cy, cz, rx, ry, rz, seg, reg, lat0 = -80, lat1 = 80, rings = 6, n = this.n) {
    const R = [];
    for (let i = 0; i <= rings; i++) {
      const lat = (lat0 + (lat1 - lat0) * i / rings) * Math.PI / 180;
      R.push([cy + ry * Math.sin(lat), rx * Math.cos(lat), rz * Math.cos(lat), cx, cz]);
    }
    this.tube(R, seg, reg, n);
  }
  box(x0, x1, y0, y1, z0, z1, seg, reg) {
    const F = [[[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], [[x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]],
      [[x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]], [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]],
      [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]], [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]];
    for (const q of F) { const i = q.map(([x, y, z]) => this.vert(x, y, z, seg, reg)); this.idx.push(i[0], i[1], i[2], i[0], i[2], i[3]); }
  }
  geometry() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('seg', new THREE.Float32BufferAttribute(this.seg, 1));
    g.setAttribute('region', new THREE.Float32BufferAttribute(this.reg, 1));
    g.setIndex(this.idx); g.computeVertexNormals();
    return g;
  }
}

/** Body types. Joint pivots feed the pose shader: hip (x, height), knee height, shoulder (x, height), elbow height. */
const TYPES = [
  { name: 'man', hip: [.095, .92], knee: .50, sh: [.212, 1.42], elbow: 1.13, build: (b, p) => {
    for (const s of [1, -1]) {
      const x = s * .095, L = s > 0, thigh = L ? SEG.L_THIGH : SEG.R_THIGH, shin = L ? SEG.L_SHIN : SEG.R_SHIN;
      b.box(x - .05, x + .05, 0, .075, -.055, .19, shin, REG.SHOES);
      b.tube([[.07, .046, .05, x], [.28, .056, .06, x], [.5, .062, .066, x]], shin, REG.BOTTOM);
      b.tube([[.5, .064, .07, x], [.72, .077, .082, x], [.93, .088, .092, x]], thigh, REG.BOTTOM);
      const ax = s * .212, up = L ? SEG.L_UPPER : SEG.R_UPPER, fore = L ? SEG.L_FORE : SEG.R_FORE;
      b.tube([[1.13, .041, .043, ax], [1.28, .046, .048, ax], [1.43, .05, .052, ax]], up, REG.TOP);
      b.tube([[.87, .031, .033, ax], [1.0, .036, .038, ax], [1.13, .039, .041, ax]], fore, p.sleeves ? REG.TOP : REG.SKIN);
      b.ellipsoid(ax, .82, .005, .03, .055, .026, fore, REG.SKIN, -70, 70, 3, 6);
    }
    b.tube([[.86, .168, .112], [.96, .172, .116], [1.02, .162, .106]], SEG.BODY, REG.BOTTOM);
    b.tube([[1.0, .156, .1], [1.13, .162, .102], [1.28, .188, .112], [1.4, .198, .106], [1.46, .15, .082]], SEG.BODY, REG.TOP);
    b.tube([[1.44, .05, .052], [1.53, .048, .05]], SEG.BODY, REG.SKIN);
    b.ellipsoid(0, 1.625, .012, .08, .105, .095, SEG.BODY, REG.SKIN, -75, 75, 6);
    b.ellipsoid(0, 1.64, -.006, .086, .105, .1, SEG.BODY, REG.HAIR, 8, 84, 3);
  } },
  { name: 'woman', hip: [.09, .88], knee: .48, sh: [.192, 1.36], elbow: 1.08, build: (b) => {
    for (const s of [1, -1]) {
      const x = s * .09, L = s > 0, thigh = L ? SEG.L_THIGH : SEG.R_THIGH, shin = L ? SEG.L_SHIN : SEG.R_SHIN;
      b.box(x - .042, x + .042, 0, .07, -.045, .17, shin, REG.SHOES);
      b.tube([[.065, .038, .042, x], [.27, .05, .054, x], [.48, .052, .056, x]], shin, REG.SKIN);
      b.tube([[.48, .056, .06, x], [.7, .07, .074, x], [.89, .08, .084, x]], thigh, REG.SKIN);
      const ax = s * .192, up = L ? SEG.L_UPPER : SEG.R_UPPER, fore = L ? SEG.L_FORE : SEG.R_FORE;
      b.tube([[1.08, .036, .038, ax], [1.22, .041, .043, ax], [1.37, .045, .047, ax]], up, REG.TOP);
      b.tube([[.84, .027, .029, ax], [.96, .031, .033, ax], [1.08, .034, .036, ax]], fore, REG.SKIN);
      b.ellipsoid(ax, .79, .005, .027, .05, .023, fore, REG.SKIN, -70, 70, 3, 6);
    }
    // A-line skirt / dress hem at the knee, fitted top
    b.tube([[.5, .205, .185], [.72, .18, .15], [.92, .165, .115], [1.0, .15, .1]], SEG.BODY, REG.BOTTOM);
    b.tube([[.98, .14, .094], [1.1, .138, .092], [1.24, .168, .108], [1.34, .178, .1], [1.4, .135, .076]], SEG.BODY, REG.TOP);
    b.tube([[1.38, .045, .047], [1.47, .043, .045]], SEG.BODY, REG.SKIN);
    b.ellipsoid(0, 1.56, .012, .075, .1, .09, SEG.BODY, REG.SKIN, -75, 75, 6);
    b.ellipsoid(0, 1.575, -.008, .082, .1, .096, SEG.BODY, REG.HAIR, 5, 84, 3);
    b.ellipsoid(0, 1.47, -.05, .085, .12, .05, SEG.BODY, REG.HAIR, -80, 60, 3);      // long hair down the back
  } },
  { name: 'child', hip: [.065, .58], knee: .32, sh: [.145, .94], elbow: .75, build: (b) => {
    for (const s of [1, -1]) {
      const x = s * .065, L = s > 0, thigh = L ? SEG.L_THIGH : SEG.R_THIGH, shin = L ? SEG.L_SHIN : SEG.R_SHIN;
      b.box(x - .038, x + .038, 0, .06, -.04, .14, shin, REG.SHOES);
      b.tube([[.055, .033, .036, x], [.18, .038, .041, x], [.32, .042, .045, x]], shin, REG.SKIN);
      b.tube([[.32, .046, .05, x], [.46, .054, .058, x], [.59, .06, .064, x]], thigh, REG.BOTTOM);
      const ax = s * .145, up = L ? SEG.L_UPPER : SEG.R_UPPER, fore = L ? SEG.L_FORE : SEG.R_FORE;
      b.tube([[.75, .031, .033, ax], [.85, .034, .036, ax], [.95, .037, .039, ax]], up, REG.TOP);
      b.tube([[.57, .024, .026, ax], [.66, .027, .029, ax], [.75, .03, .032, ax]], fore, REG.SKIN);
      b.ellipsoid(ax, .53, .004, .023, .04, .02, fore, REG.SKIN, -70, 70, 3, 6);
    }
    b.tube([[.55, .115, .08], [.62, .118, .082], [.67, .112, .078]], SEG.BODY, REG.BOTTOM);
    b.tube([[.65, .11, .075], [.8, .12, .08], [.93, .128, .076], [.97, .1, .06]], SEG.BODY, REG.TOP);
    b.tube([[.96, .038, .04], [1.02, .036, .038]], SEG.BODY, REG.SKIN);
    b.ellipsoid(0, 1.11, .01, .078, .095, .088, SEG.BODY, REG.SKIN, -75, 75, 6);
    b.ellipsoid(0, 1.125, -.005, .083, .096, .092, SEG.BODY, REG.HAIR, 10, 84, 3);
  } },
  { name: 'backpack', hip: [.095, .92], knee: .50, sh: [.212, 1.42], elbow: 1.13, build: (b, p) => {
    TYPES[0].build(b, p);
    b.box(-.15, .15, 1.06, 1.42, -.27, -.1, SEG.BODY, REG.BAG);
  } },
];

const PALETTE = {
  top: ['#1F2A44', '#2A2A2B', '#E8E5DE', '#8C8F93', '#6E7B58', '#7A2E2E', '#3F5D7D', '#C9B79C', '#B8433A', '#D1A23A', '#35593D', '#57496B',
    '#F1EEE7', '#44403C', '#9FB3C8', '#A45A3D'],
  bottom: ['#2E3A4F', '#44536F', '#1E1E1F', '#626366', '#B9A77F', '#3D3126', '#2A3342', '#56504A'],
  skirt: ['#2B2B2C', '#5A3E5D', '#7B8FA6', '#8E3B46', '#C9B79C', '#1F2A44', '#E3DDD2', '#4F6B4A'],
  skin: ['#EAC8AC', '#DDB191', '#CF9E7C', '#C18B69', '#A87251', '#8A5A3E'],
  hair: ['#1B1511', '#2B1F17', '#3B2A1F', '#4E392A', '#6A5746', '#8F8A85', '#B7B2AB', '#A58A62'],
};
const pick = (r, list, weights) => {
  if (!weights) return list[Math.floor(r() * list.length) % list.length];
  let t = r() * weights.reduce((a, b) => a + b, 0);
  for (let i = 0; i < list.length; i++) { t -= weights[i]; if (t <= 0) return list[i]; }
  return list[list.length - 1];
};
const lin = (hex) => new THREE.Color(hex);          // THREE.Color parses sRGB hex into the linear working space

function peopleMaterial(type, uniforms) {
  const m = new THREE.MeshStandardMaterial({ roughness: .82, metalness: 0, envMapIntensity: 1.0 });
  const [hx, hy] = type.hip, [sx, sy] = type.sh;
  m.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader.replace('#include <common>', `#include <common>
      attribute float seg; attribute float region;
      attribute vec4 pMotion; attribute vec4 pTop; attribute vec4 pBottom; attribute vec4 pSkin; attribute vec4 pHair;
      uniform float peopleTime;
      varying vec3 vPeopleColor; varying float vSunVis; varying float vFade;
      vec3 rotX(vec3 p, vec3 o, float a){ vec3 q=p-o; float c=cos(a), s=sin(a); return o+vec3(q.x, c*q.y-s*q.z, s*q.y+c*q.z); }
      vec3 rotXn(vec3 n, float a){ float c=cos(a), s=sin(a); return vec3(n.x, c*n.y-s*n.z, s*n.y+c*n.z); }`)
      .replace('#include <beginnormal_vertex>', `#include <beginnormal_vertex>
      // ---- pose: joint angles for this person and moment (flexion > 0 = forward) ----
      float mode = pMotion.w, amp = pMotion.z;
      float ph = pMotion.x + 6.2831853 * pMotion.y * peopleTime;
      float run = step(2.5, mode) * step(mode, 3.5), sit = step(1.5, mode) * step(mode, 2.5);
      float stand = step(.5, mode) * step(mode, 1.5);
      float idle = .03 * sin(peopleTime * .9 + pMotion.x);                  // standing: slow weight shift
      float hipL = amp * (.42 + .16 * run) * sin(ph), hipR = -hipL;
      float kneeL = amp * (.75 + .6 * run) * max(0., cos(ph)) + .08 * amp, kneeR = amp * (.75 + .6 * run) * max(0., -cos(ph)) + .08 * amp;
      float shL = -amp * (.34 + .1 * run) * sin(ph) + .04, shR = -shL + .08;
      float elbow = .22 + .1 * amp + 1.1 * run + stand * .08;
      if (sit > .5) { hipL = hipR = 1.5; kneeL = kneeR = 1.52; shL = shR = .42; elbow = .95; }
      if (stand > .5) { hipL = idle; hipR = -idle; kneeL = kneeR = .03; shL = .05 + idle; shR = .05 - idle; }
      vec3 hipP = vec3(${hx.toFixed(3)}, ${hy.toFixed(3)}, 0.), kneeY = vec3(0., ${type.knee.toFixed(3)}, 0.);
      vec3 shP = vec3(${sx.toFixed(3)}, ${sy.toFixed(3)}, 0.), elbowY = vec3(0., ${type.elbow.toFixed(3)}, 0.);
      float sd = (seg == 1. || seg == 2. || seg == 5. || seg == 6.) ? 1. : -1.;
      vec3 P = position, N = objectNormal;
      if (seg >= 1. && seg <= 4.) {
        float hipA = sd > 0. ? hipL : hipR, kneeA = sd > 0. ? kneeL : kneeR;
        vec3 ho = vec3(sd * hipP.x, hipP.y, 0.), ko = vec3(sd * hipP.x, kneeY.y, 0.);
        if (seg == 2. || seg == 4.) { P = rotX(P, ko, kneeA); N = rotXn(N, kneeA); }
        P = rotX(P, ho, -hipA); N = rotXn(N, -hipA);
      } else if (seg >= 5.) {
        float shA = sd > 0. ? shL : shR;
        vec3 so = vec3(sd * shP.x, shP.y, 0.), eo = vec3(sd * shP.x, elbowY.y, 0.);
        if (seg == 6. || seg == 8.) { P = rotX(P, eo, -elbow); N = rotXn(N, -elbow); }
        P = rotX(P, so, -shA); N = rotXn(N, -shA);
      }
      // body bob while walking/running, forward lean when running
      P.y += amp * (.018 + .02 * run) * (cos(2. * ph) * .5 + .5);
      if (run > .5) { P = rotX(P, vec3(0.), .12); N = rotXn(N, .12); }
      objectNormal = N;
      vec3 c = region < .5 ? pSkin.rgb : region < 1.5 ? pHair.rgb : region < 2.5 ? pTop.rgb : region < 3.5 ? pBottom.rgb
             : region < 4.5 ? vec3(mix(.035, .62, pHair.w)) : pBottom.rgb * .55 + vec3(.01);
      vPeopleColor = c; vSunVis = pTop.w; vFade = pSkin.w;`)
      .replace('#include <begin_vertex>', `vec3 transformed = P;`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vPeopleColor; varying float vSunVis; varying float vFade;`)
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        // route ends: stable screen-door dissolve, like the traffic
        if (vFade < fract(dot(floor(gl_FragCoord.xy), vec2(.754877666, .569840296)))) discard;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        diffuseColor.rgb = vPeopleColor;`)
      .replace('#include <lights_fragment_begin>', THREE.ShaderChunk.lights_fragment_begin.replace(
        'getDirectionalLightInfo( directionalLight, directLight );',
        'getDirectionalLightInfo( directionalLight, directLight );\n\t\tdirectLight.color *= vSunVis;'));
  };
  m.customProgramCacheKey = () => 'nk-people-' + type.name;
  return m;
}

function shadowMaterial(length) {
  const m = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, toneMapped: false });
  m.onBeforeCompile = shader => {
    shader.vertexShader = shader.vertexShader.replace('#include <common>', `#include <common>
      attribute vec2 shadowState; varying vec2 vLocal; varying vec2 vShadowState;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vLocal = position.xz; vShadowState = shadowState;`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>
      varying vec2 vLocal; varying vec2 vShadowState;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        // sun shadow: a capsule from the feet (local z = -L/2) away from the sun; contact shading at the feet
        float L = ${length.toFixed(3)};
        vec2 a = vec2(0., -L * .5), b = vec2(0., L * .5), pa = vLocal - a, ba = b - a;
        float h = clamp(dot(pa, ba) / dot(ba, ba), 0., 1.);
        float r = mix(.15, .21, smoothstep(.12, .6, h)) - .07 * smoothstep(.8, 1., h);
        float d = length(pa - ba * h) - r;
        float sunShadow = (1. - smoothstep(-.06, .1, d)) * .52 * vShadowState.x;
        float contact = (1. - smoothstep(0., .38, length(vLocal - a))) * .26;
        diffuseColor = vec4(vec3(.022, .032, .045), max(sunShadow, contact) * vShadowState.y);
        if (diffuseColor.a < .003) discard;`);
  };
  m.customProgramCacheKey = () => 'nk-people-shadow-' + length.toFixed(2);
  return m;
}

function samplePath(path, distance) {
  const L = path.length, closed = path.closed;
  let s = closed ? ((distance % L) + L) % L : Math.min(L, Math.max(0, distance));
  const rows = path.samples;
  let lo = 0, hi = rows.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (rows[mid][2] <= s) lo = mid; else hi = mid; }
  const a = rows[lo], b = rows[hi], t = (s - a[2]) / Math.max(1e-5, b[2] - a[2]);
  const dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz) || 1;
  return { x: a[0] + dx * t, z: a[1] + dz * t, tx: dx / len, tz: dz / len, shade: a.length > 3 ? a[3] + (b[3] - a[3]) * t : 1, s };
}

const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), V = new THREE.Vector3(), S = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);

export class People {
  static async load(scene, version, mobile) {
    const r = await fetch(`./assets/people.json?v=${version}`);
    if (!r.ok) throw new Error('people.json unavailable');
    return new People(scene, await r.json(), mobile);
  }

  constructor(scene, data, mobile) {
    this.data = data; this.paths = data.paths;
    this.uniforms = { peopleTime: { value: 0 } };
    // everyone: [kind, type, ...]; phones show every other walker / idle person and all children
    const persons = [];
    const keep = (i) => !mobile || i % 2 === 0;
    data.walkers.forEach((w, i) => { if (keep(i)) persons.push({ kind: 'walk', path: this.paths[w[0]], offset: w[1], dir: w[2], speed: w[3], lateral: w[4], type: w[5], seed: w[6], mode: w[7] }); });
    data.idle.forEach((p, i) => { if (keep(i)) persons.push({ kind: 'idle', x: p[0], z: p[1], yaw: p[2], type: p[3], seed: p[4], mode: p[5], y: p[6], shade: p[7] }); });
    (data.kids || []).forEach(k => persons.push({ kind: 'kid', cx: k[0], cz: k[1], rx: k[2], rz: k[3], type: 2, seed: k[4], mode: 0, shade: k[5] }));
    this.persons = persons;
    const n = mobile ? 6 : 8;
    this.groups = TYPES.map((type, ti) => {
      const members = persons.filter(p => p.type === ti);
      if (!members.length) return null;
      const b = new FigureBuilder(n); type.build(b, { sleeves: true });
      const geometry = b.geometry();
      const count = members.length;
      const attr = (k) => new THREE.InstancedBufferAttribute(new Float32Array(count * k), k);
      const motion = attr(4), top = attr(4), bottom = attr(4), skin = attr(4), hair = attr(4);
      top.setUsage(THREE.DynamicDrawUsage); skin.setUsage(THREE.DynamicDrawUsage);
      members.forEach((p, i) => {
        const r = mulberry32(p.seed * 7919 + 17);
        const run = p.mode === 3, sit = p.mode === 2, stand = p.mode === 1;
        const freq = run ? p.speed / 2.3 : p.kind === 'walk' ? p.speed / 1.42 : p.kind === 'kid' ? 1.25 : 0;
        motion.setXYZW(i, r() * 6.2832, freq, (sit || stand) ? 0 : run ? 1.25 : p.kind === 'kid' ? 1.1 : 1, p.mode);
        const topCol = lin(pick(r, PALETTE.top)), botCol = lin(pick(r, ti === 1 ? PALETTE.skirt : PALETTE.bottom));
        const skinCol = lin(pick(r, PALETTE.skin, [5, 6, 4, 3, 1.2, .6]));
        const hairCol = lin(pick(r, PALETTE.hair, [5, 6, 4, 2.5, 1.2, 1, .8, .7]));
        if (ti === 3) botCol.copy(lin(pick(r, PALETTE.bottom)));
        top.setXYZW(i, topCol.r, topCol.g, topCol.b, 1);
        bottom.setXYZW(i, botCol.r, botCol.g, botCol.b, 0);
        skin.setXYZW(i, skinCol.r, skinCol.g, skinCol.b, 1);
        hair.setXYZW(i, hairCol.r, hairCol.g, hairCol.b, r() < .3 ? 1 : 0);   // w: white trainers
        p.scale = (ti === 2 ? .85 + r() * .35 : ti === 1 ? .95 + r() * .09 : .96 + r() * .1);
        p.index = i;
      });
      const group = { type, members, mesh: null, top, skin };
      members.forEach(p => { p.group = group; });
      for (const [k, a] of Object.entries({ pMotion: motion, pTop: top, pBottom: bottom, pSkin: skin, pHair: hair })) geometry.setAttribute(k, a);
      const mesh = new THREE.InstancedMesh(geometry, peopleMaterial(type, this.uniforms), count);
      mesh.name = 'People ' + type.name; mesh.frustumCulled = false; mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      scene.add(mesh);
      group.mesh = mesh;
      return group;
    }).filter(Boolean);
    // soft sun shadows (one quad per person, oriented away from the sun)
    this.shadowLen = 3.3;
    const sg = new THREE.PlaneGeometry(1.1, this.shadowLen + 1.1); sg.rotateX(-Math.PI / 2);
    this.shadowState = new THREE.InstancedBufferAttribute(new Float32Array(persons.length * 2), 2);
    this.shadowState.setUsage(THREE.DynamicDrawUsage); sg.setAttribute('shadowState', this.shadowState);
    this.shadows = new THREE.InstancedMesh(sg, shadowMaterial(this.shadowLen), persons.length);
    this.shadows.name = 'People soft sun shadows'; this.shadows.frustumCulled = false; this.shadows.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(this.shadows);
    this.setSun(new THREE.Vector3(-.82, .47, .37));
    this.initialised = false;
  }

  /** sunDirection: towards the sun (three.js axes). Shadow length follows the sun's elevation. */
  setSun(sunDirection) {
    const d = sunDirection.clone().normalize();
    const h = Math.hypot(d.x, d.z) || 1;
    this.away = new THREE.Vector2(-d.x / h, -d.z / h);                    // shadows fall away from the sun
    this.shadowScale = Math.min(3, (1 / Math.tan(Math.asin(Math.min(.999, d.y)))) * 1.7 / this.shadowLen);
    this.shadowYaw = Math.atan2(this.away.x, this.away.y);
  }

  place(p, x, z, yaw, shade, fade, i) {
    const g = p.group;
    // sitting: the pelvis rests on the seat (p.y = seat height above the ground)
    const y = GROUND + (p.mode === 2 ? (p.y ?? .45) + .1 - g.type.hip[1] * p.scale : 0);
    Q.setFromAxisAngle(UP, yaw); S.setScalar(p.scale); V.set(x, y, z);
    g.mesh.setMatrixAt(p.index, M.compose(V, Q, S));
    g.top.setW(p.index, shade); g.skin.setW(p.index, fade);
    // shadow quad: its local z runs from the feet (-L/2) away from the sun (+L/2), so its centre sits half a
    // shadow length from the feet; scaled with the person (sitting people cast shorter shadows)
    const len = this.shadowLen * this.shadowScale * p.scale * (p.mode === 2 ? .7 : 1);
    Q.setFromAxisAngle(UP, this.shadowYaw); S.set(p.scale, 1, len / this.shadowLen);
    V.set(x + this.away.x * len * .5, GROUND + .004, z + this.away.y * len * .5);
    this.shadows.setMatrixAt(i, M.compose(V, Q, S));
    this.shadowState.setXY(i, shade, fade);                            // shade = sun visibility 0..1 (nk_people.py)
  }

  update(time) {
    this.uniforms.peopleTime.value = time;
    let i = 0;
    for (const p of this.persons) {
      if (p.kind === 'walk') {
        const s = p.offset + p.dir * p.speed * time;
        const path = p.path, L = path.length;
        let d = s, fade = 1;
        if (!path.closed) {
          // open routes: walk to the end, dissolve, reappear at the start
          const span = L + 4;
          d = ((s % span) + span) % span - 2;
          const edge = Math.min(d + 2, L + 2 - d) / 2.5;
          fade = Math.max(0, Math.min(1, edge));
          if (p.dir < 0) d = L - d;
        }
        const q = samplePath(path, d);
        const tx = q.tx * p.dir, tz = q.tz * p.dir;
        const x = q.x - tz * p.lateral, z = q.z + tx * p.lateral;          // keep to one side of the path
        this.place(p, x, z, Math.atan2(tx, tz), q.shade, fade, i);
      } else if (p.kind === 'kid') {
        const r = mulberry32(p.seed), a = r() * 6.28, b = r() * 6.28, w1 = .35 + r() * .3, w2 = .45 + r() * .3;
        const t = time;
        const x = p.cx + p.rx * Math.sin(w1 * t + a), z = p.cz + p.rz * Math.sin(w2 * t + b);
        const vx = p.rx * w1 * Math.cos(w1 * t + a), vz = p.rz * w2 * Math.cos(w2 * t + b);
        this.place(p, x, z, Math.atan2(vx, vz), p.shade, 1, i);
      } else if (!this.initialised) {
        this.place(p, p.x, p.z, p.yaw, p.shade, 1, i);
      }
      i++;
    }
    this.initialised = true;
    for (const g of this.groups) { g.mesh.instanceMatrix.needsUpdate = true; g.top.needsUpdate = true; g.skin.needsUpdate = true; }
    this.shadows.instanceMatrix.needsUpdate = true; this.shadowState.needsUpdate = true;
    return true;
  }

  diagnostics() {
    const by = k => this.persons.filter(p => p.kind === k).length;
    return { people: this.persons.length, walking: by('walk'), idle: by('idle'), kids: by('kid'),
      triangles: this.groups.reduce((s, g) => s + g.mesh.count * g.mesh.geometry.index.count / 3, 0) };
  }
}
