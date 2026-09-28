import * as THREE from 'three';

/** Continuous canopy interpolation (8 azimuths x 3 elevations per species, captured in Cycles
 *  under the same sun as the baked lighting); all shadows are baked in world space.
 *  Billboarding and the choice of view happen in the vertex shader: the instance matrices are static
 *  (canopy centre + size), so a camera move costs three uniforms instead of a pass over 12,000 trees. */
function canopyMaterial(atlas, profile, uniforms) {
  const material=new THREE.MeshBasicMaterial({map:atlas,alphaTest:.16,alphaToCoverage:true,side:THREE.DoubleSide,toneMapped:false});
  material.onBeforeCompile=shader=>{
    Object.assign(shader.uniforms,uniforms);
    shader.vertexShader=shader.vertexShader.replace('#include <common>',`#include <common>
      attribute vec2 canopyWind; attribute float canopyRot; varying vec2 vCanopyView;
      uniform float windTime; uniform vec2 windScreen; uniform vec3 billboardRight; uniform vec3 billboardUp;`)
      .replace('#include <begin_vertex>',`#include <begin_vertex>
        // Root-anchored bend; coherent breeze plus independent branch flutter.
        float height=clamp((position.y*${profile.captureSize.toFixed(5)}+${profile.center[2].toFixed(5)})/${profile.height.toFixed(5)},0.,1.);
        float bend=pow(smoothstep(.18,1.,height),1.35);
        float gust=.050*sin(windTime*.78+canopyWind.x)+.016*sin(windTime*1.31+canopyWind.y);
        transformed.xy+=windScreen*bend*gust;
        transformed.x+=.004*sin(windTime*2.7+position.y*16.+canopyWind.y)*smoothstep(.40,.90,height);
      `)
      .replace('#include <project_vertex>',`
        // Camera-facing quad around the canopy centre; view cell from the direction to the camera.
        vec4 nkCenter=modelMatrix*instanceMatrix*vec4(0.,0.,0.,1.);
        float nkScale=length(instanceMatrix[0].xyz);
        vec3 nkDir=cameraPosition-nkCenter.xyz;
        vCanopyView=vec2(mod((atan(nkDir.x,nkDir.z)-canopyRot)*1.2732395,8.),
                         clamp((degrees(atan(nkDir.y,length(nkDir.xz)))-25.)/25.,0.,2.));
        vec4 mvPosition=viewMatrix*vec4(nkCenter.xyz+(billboardRight*transformed.x+billboardUp*transformed.y)*nkScale,1.);
        gl_Position=projectionMatrix*mvPosition;
      `);
    shader.fragmentShader=shader.fragmentShader.replace('#include <map_pars_fragment>',`#include <map_pars_fragment>
      varying vec2 vCanopyView;
      vec4 canopySample(float column,float row,vec2 uv){
        vec2 cell=clamp(uv,vec2(.003),vec2(.997));
        vec4 c=texture2D(map,vec2((mod(column,8.)+cell.x)/8.,1.-(row+1.-cell.y)/3.));
        return vec4(c.rgb*c.a,c.a);
      }`)
      .replace('#include <map_fragment>',`
        float az=floor(vCanopyView.x), el=floor(vCanopyView.y);
        vec2 blend=fract(vCanopyView);
        vec4 low=mix(canopySample(az,el,vMapUv),canopySample(az+1.,el,vMapUv),blend.x);
        vec4 high=mix(canopySample(az,min(2.,el+1.),vMapUv),canopySample(az+1.,min(2.,el+1.),vMapUv),blend.x);
        vec4 canopy=mix(low,high,blend.y);
        diffuseColor*=vec4(canopy.rgb/max(canopy.a,.00001),canopy.a);
      `);
  };
  material.customProgramCacheKey=()=>'nk-canopy-gpu-'+profile.prefix;
  return material;
}

const BREEZE=new THREE.Vector3(.82,0,.57),RIGHT=new THREE.Vector3(),UP=new THREE.Vector3();
const matrix=new THREE.Matrix4(),color=new THREE.Color();

class Species {
  constructor(scene,rows,profile,atlas,uniforms){
    Object.assign(this,{rows,profile});
    // 1 x 4 segments: enough rows for the root-anchored bend, 8 triangles per tree.
    const geometry=new THREE.PlaneGeometry(1,1,1,4);
    const wind=new THREE.InstancedBufferAttribute(new Float32Array(rows.length*2),2);
    const rot=new THREE.InstancedBufferAttribute(new Float32Array(rows.length),1);
    this.mesh=new THREE.InstancedMesh(geometry,canopyMaterial(atlas,profile,uniforms),rows.length);
    this.mesh.frustumCulled=false;this.mesh.name='Trees '+profile.prefix;
    const up=new THREE.Vector3(0,1,0);
    rows.forEach((row,i)=>{
      wind.setXY(i,row.position[0]*.037-row.position[1]*.029,i*.713);rot.setX(i,row.rotation);
      row.world=new THREE.Vector3(row.position[0],row.position[2],-row.position[1]);
      const center=new THREE.Vector3(profile.center[0],profile.center[2],-profile.center[1]).multiplyScalar(row.scale).applyAxisAngle(up,row.rotation);
      row.center=row.world.clone().add(center);
      const size=profile.captureSize*row.scale;
      this.mesh.setMatrixAt(i,matrix.makeScale(size,size,size).setPosition(row.center));
      this.mesh.setColorAt(i,color.setRGB(...(row.tint||[1,1,1])));
    });
    geometry.setAttribute('canopyWind',wind);geometry.setAttribute('canopyRot',rot);
    scene.add(this.mesh);
  }
}

export class Landscape {
  /** mobile: half-resolution atlases (128 px views). */
  static async load(scene, loader, mobile, version) {
    const asset=name=>`./assets/${name}?v=${version}`;
    const [rows, manifest] = await Promise.all([
      fetch(asset('tree-instances.json')).then(r=>r.json()),
      fetch(asset('tree/species.json')).then(r=>r.json()),
    ]);
    const uniforms={windTime:{value:0},windScreen:{value:new THREE.Vector2(1,0)},
      billboardRight:{value:new THREE.Vector3(1,0,0)},billboardUp:{value:new THREE.Vector3(0,1,0)}};
    const species=[];
    await Promise.all(manifest.species.map(async sp=>{
      const members=rows.filter(r=>(r.species||manifest.species[0].name)===sp.name);
      if(!members.length)return;
      let atlas;
      try{atlas=await new THREE.TextureLoader().loadAsync(asset(mobile?sp.atlasMobile:sp.atlas));}
      catch(error){console.warn('Tree atlas unavailable, skipping',sp.name,error);return;}
      atlas.colorSpace=THREE.SRGBColorSpace;atlas.anisotropy=8;
      species.push(new Species(scene,members,sp.profile,atlas,uniforms));
    }));
    return new Landscape(species,rows,uniforms);
  }
  constructor(species,rows,uniforms){
    Object.assign(this,{species,rows,uniforms,windTime:uniforms.windTime,windScreen:uniforms.windScreen});
    this.lastQ=new THREE.Quaternion(0,0,0,0);
  }
  update(camera){
    // Only the camera's orientation matters here; positions are handled in the shader.
    if(Math.abs(this.lastQ.dot(camera.quaternion))>.99999999)return false;
    this.lastQ.copy(camera.quaternion);
    const right=RIGHT.set(1,0,0).applyQuaternion(camera.quaternion),up=UP.set(0,1,0).applyQuaternion(camera.quaternion);
    this.uniforms.billboardRight.value.copy(right);this.uniforms.billboardUp.value.copy(up);
    this.windScreen.value.set(right.dot(BREEZE),up.dot(BREEZE));
    return true;
  }
  animate(time){this.windTime.value=time;return true;}
}
