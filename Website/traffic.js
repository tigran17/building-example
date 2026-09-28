import * as THREE from 'three';
import { sampleLane } from './traffic-path.js?v=0.12.0';

const PAINTS={carWhite:'#dedbd2',carSilver:'#8e9ea4',carBlue:'#164b68',carDark:'#242c32',carRed:'#7f242b'};
const PAINT_COLORS=Object.fromEntries(Object.entries(PAINTS).map(([k,v])=>[k,new THREE.Color(v)]));
const WHEELS=[[-.905,-1.38],[-.905,1.38],[.905,-1.38],[.905,1.38]];
// Cars switch to the ~140-triangle proxy beyond this distance (with a little hysteresis).
const NEAR_IN=70,NEAR_OUT=78;
const object=new THREE.Object3D(),wheel=new THREE.Object3D(),color=new THREE.Color();
const partMatrix=new THREE.Matrix4();

function fadeShader(material){
  material.onBeforeCompile=shader=>{
    shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nattribute float trafficFade; varying float vTrafficFade;')
      .replace('#include <begin_vertex>','#include <begin_vertex>\nvTrafficFade=trafficFade;');
    shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nvarying float vTrafficFade;')
      .replace('#include <clipping_planes_fragment>',`#include <clipping_planes_fragment>
        // Stable screen-door coverage only at the remote lane boundaries.
        float threshold=fract(dot(floor(gl_FragCoord.xy),vec2(.754877666,.569840296)));
        if(vTrafficFade<threshold)discard;`);
  };
  material.customProgramCacheKey=()=> 'traffic-boundary-coverage-v1';
}

/** Phones: the same look without the clearcoat lobe (cars are a few dozen pixels there). */
function liteMaterial(source){
  const m=new THREE.MeshStandardMaterial({name:source.name,color:source.color,metalness:source.metalness,roughness:source.roughness});
  return m;
}

export class Traffic {
  static async load(scene,loader,version,lite=false){
    const [gltf,response]=await Promise.all([loader.loadAsync(`./assets/vehicles-lod.glb?v=${version}`),fetch(`./assets/traffic-routes.json?v=${version}`)]);
    if(!response.ok)throw new Error('Traffic routes could not be loaded');
    return new Traffic(scene,gltf.scene,await response.json(),lite);
  }
  constructor(scene,library,data,lite){
    this.data=data;
    // Sun visibility is precomputed in Blender (nk_trafficshade.py): per parked car and per lane sample.
    this.rows=data.parked.map(row=>({...row,x:row.position[0],z:-row.position[1],angle:row.rotation,fade:1,travel:0,shade:row.shade??1,lod:1}));
    for(const [laneIndex,lane] of data.lanes.entries())for(let i=0;i<lane.count;i++){
      this.rows.push({style:(i+laneIndex)%3===0?'suv':'sedan',paint:Object.keys(PAINTS)[(i+laneIndex*2)%5],
        lane,offset:(i+.35+laneIndex*.12)/lane.count*lane.length,shade:1,lod:1,steer:0});
    }
    for(const row of this.rows)row.matrix=new THREE.Matrix4();
    this.batches=[];library.updateMatrixWorld(true);
    library.traverse(source=>{
      if(!source.isMesh)return;
      const [nameModel,namePart,nameLod]=source.name.split('__');
      const style=source.userData.vehicleModel||nameModel,kind=source.userData.vehiclePart||namePart;
      const lod=source.userData.vehicleLod??(nameLod==='lod1'?1:0);
      const isWheel=style==='wheel';
      const rows=isWheel?this.rows:this.rows.filter(row=>row.style===style);
      const count=rows.length*(isWheel?4:1),geometry=source.geometry.clone();
      geometry.applyMatrix4(source.matrixWorld);
      const fade=new THREE.InstancedBufferAttribute(new Float32Array(count).fill(1),1);
      fade.setUsage(THREE.DynamicDrawUsage);geometry.setAttribute('trafficFade',fade);
      const material=lite?liteMaterial(source.material):source.material.clone();fadeShader(material);
      material.envMapIntensity=1.35;
      if(kind==='lamps'){material.emissive=new THREE.Color('#cddfff');material.emissiveIntensity=.15;}
      if(kind==='tail'){material.emissive=new THREE.Color('#a21e19');material.emissiveIntensity=.2;}
      const mesh=new THREE.InstancedMesh(geometry,material,count);mesh.name=`Traffic ${style}__${kind}__lod${lod}`;
      mesh.frustumCulled=false;mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);mesh.count=0;
      mesh.setColorAt(0,color.set(1,1,1));mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
      scene.add(mesh);
      this.batches.push({mesh,rows,isWheel,kind,lod,fade,paint:kind==='paint'});
    });
    const geometry=new THREE.PlaneGeometry(10,10);geometry.rotateX(-Math.PI/2);
    this.shadowFade=new THREE.InstancedBufferAttribute(new Float32Array(this.rows.length).fill(1),1);geometry.setAttribute('trafficFade',this.shadowFade);
    this.shadowProjection=new THREE.InstancedBufferAttribute(new Float32Array(this.rows.length*3),3);geometry.setAttribute('shadowProjection',this.shadowProjection);
    const material=new THREE.MeshBasicMaterial({transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2,toneMapped:false});
    material.onBeforeCompile=shader=>{
      shader.vertexShader=shader.vertexShader.replace('#include <common>',`#include <common>
        attribute float trafficFade; attribute vec3 shadowProjection;
        varying vec3 vShadowProjection; varying vec2 vShadowPoint; varying float vShadowFade;`)
        .replace('#include <begin_vertex>',`#include <begin_vertex>
          vShadowProjection=shadowProjection;vShadowPoint=position.xz;vShadowFade=trafficFade;`);
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
        varying vec3 vShadowProjection; varying vec2 vShadowPoint; varying float vShadowFade;
        float bodyDistance(vec2 p){vec2 q=abs(p)-vec2(.67,1.78);return length(max(q,0.))+min(max(q.x,q.y),0.)-.20;}`)
        .replace('#include <color_fragment>',`#include <color_fragment>
          // Soft projection of the body envelope in the approved sun direction.
          // It travels with the car and narrows in building shade; no shadow map.
          float d=10.;for(int i=0;i<6;i++)d=min(d,bodyDistance(vShadowPoint-vShadowProjection.xy*float(i)/5.));
          float projectedShade=(1.-smoothstep(-.12,.35,d))*.30*vShadowProjection.z;
          float contact=(1.-smoothstep(-.10,.32,bodyDistance(vShadowPoint)))*.28;
          diffuseColor=vec4(vec3(.025,.037,.051),max(projectedShade,contact)*vShadowFade);
          if(diffuseColor.a<.002)discard;`);
    };
    material.customProgramCacheKey=()=> 'soft-sun-aligned-vehicle-shadows-v1';
    this.shadows=new THREE.InstancedMesh(geometry,material,this.rows.length);this.shadows.frustumCulled=false;this.shadows.name='Moving soft vehicle contact shadows';
    this.shadows.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(this.shadows);
  }
  /** sunDirection: unit vector towards the sun (three.js axes). */
  setSun(sunDirection){this.sunDirection=sunDirection.clone().normalize();}
  update(time,camera){
    const cx=camera?camera.position.x:0,cy=camera?camera.position.y:0,cz=camera?camera.position.z:0;
    for(const row of this.rows){
      if(row.lane){
        row.travel=time*row.lane.speed;Object.assign(row,sampleLane(row.lane,row.offset+row.travel));
        const before=sampleLane(row.lane,row.offset+row.travel-1.4),after=sampleLane(row.lane,row.offset+row.travel+1.4);
        const turn=Math.atan2(Math.sin(after.angle-before.angle),Math.cos(after.angle-before.angle));
        row.steer=THREE.MathUtils.clamp(Math.atan(2.76*turn/2.8),-.45,.45);
      }
      const d=camera?Math.hypot(row.x-cx,1-cy,row.z-cz):Infinity;
      row.lod=row.lod===0?(d>NEAR_OUT?1:0):(d<NEAR_IN?0:1);
      object.position.set(row.x,.255,row.z);object.rotation.set(0,row.angle,0);object.scale.setScalar(1);object.updateMatrix();
      row.matrix.copy(object.matrix);
    }
    for(const batch of this.batches){
      let index=0;const mesh=batch.mesh;
      for(const row of batch.rows){
        if(row.lod!==batch.lod||row.fade<.001)continue;
        if(batch.isWheel){
          for(const [x,z] of WHEELS){
            wheel.position.set(x,.35,z);wheel.rotation.set(row.travel/.35,z<0?(row.steer||0):0,0,'YXZ');wheel.scale.setScalar(1);wheel.updateMatrix();
            mesh.setMatrixAt(index,partMatrix.multiplyMatrices(row.matrix,wheel.matrix));
            mesh.setColorAt(index,color.setScalar(row.shade));batch.fade.setX(index++,row.fade);
          }
        }else{
          mesh.setMatrixAt(index,row.matrix);
          if(batch.paint)color.copy(PAINT_COLORS[row.paint]).multiplyScalar(row.shade);else color.setScalar(row.shade);
          mesh.setColorAt(index,color);batch.fade.setX(index++,row.fade);
        }
      }
      mesh.count=index;
      mesh.instanceMatrix.needsUpdate=true;mesh.instanceColor.needsUpdate=true;batch.fade.needsUpdate=true;
    }
    const sun=this.sunDirection||new THREE.Vector3(-.82,.47,.37);
    const dx0=-sun.x/sun.y,dz0=-sun.z/sun.y;
    this.rows.forEach((row,index)=>{
      object.position.set(row.x,.266,row.z);object.rotation.set(0,row.angle,0);object.scale.setScalar(row.fade<.01?0:1);object.updateMatrix();
      this.shadows.setMatrixAt(index,object.matrix);
      // Fade contact shadows with their car as it enters/leaves the route.
      this.shadowFade.setX(index,row.fade);
      const height=row.style==='suv'?1.3:1.05,dx=dx0*height,dz=dz0*height;
      this.shadowProjection.setXYZ(index,Math.cos(row.angle)*dx-Math.sin(row.angle)*dz,Math.sin(row.angle)*dx+Math.cos(row.angle)*dz,row.shade);
    });
    this.shadows.instanceMatrix.needsUpdate=true;this.shadowFade.needsUpdate=true;this.shadowProjection.needsUpdate=true;
    return true;
  }
  diagnostics(){
    const near=this.rows.filter(r=>r.lod===0).length;
    return {models:this.data.models.length,parked:this.data.parked.length,moving:this.rows.filter(r=>r.lane).length,near,far:this.rows.length-near,
      drawCalls:this.batches.filter(b=>b.mesh.count>0).length+1,
      triangles:this.batches.reduce((s,b)=>s+b.mesh.count*(b.mesh.geometry.index?b.mesh.geometry.index.count:b.mesh.geometry.attributes.position.count)/3,0),
      cars:this.rows.map(r=>({style:r.style,lane:r.lane?.id||'parked',x:r.x,z:r.z,angle:r.angle,fade:r.fade,travel:r.travel,shade:r.shade,lod:r.lod}))};
  }
}
