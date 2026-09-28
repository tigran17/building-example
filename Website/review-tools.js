import * as THREE from 'three';

/** Opt-in local QA controls, available only with ?qa=1. */
export class ReviewTools {
  constructor(renderer,scene,camera,controls,compact,invalidate,updateLandscape,version,motionDiagnostics,landscape){
    Object.assign(this,{renderer,scene,camera,controls,compact,invalidate,updateLandscape});
    const panel=document.createElement('section');panel.id='quality-review';panel.setAttribute('aria-label','Rendering diagnostics');
    Object.assign(panel.style,{position:'fixed',bottom:'18px',left:'14px',zIndex:50,width:'290px',maxHeight:'48vh',overflow:'auto',padding:'15px',background:'#17392fed',color:'white',borderRadius:'12px',font:'12px/1.5 monospace',boxShadow:'0 6px 28px #0003'});
    panel.innerHTML='<strong>Rendering diagnostics</strong><p>Local browser measurements</p><button id="orbit-benchmark">Run 360° orbit test</button> <button id="stability-check">Check stationary stability</button> <button id="record-orbit">Record orbit preview</button><pre id="review-result" style="white-space:pre-wrap;margin:12px 0 0">Ready</pre>';
    document.body.append(panel);this.panel=panel;this.output=panel.querySelector('pre');
    panel.querySelector('#orbit-benchmark').onclick=()=>this.startOrbit();
    panel.querySelector('#stability-check').onclick=()=>this.checkStability();
    panel.querySelector('#record-orbit').onclick=()=>this.startOrbit(true);
    if(motionDiagnostics){
      const closeup=document.createElement('button');closeup.textContent='Inspect parked cars';
      closeup.onclick=()=>{camera.position.set(12,5.3,149);controls.target.set(5,.8,140);controls.update();invalidate();};
      const snapshot=document.createElement('button');snapshot.textContent='Inspect motion state';snapshot.onclick=()=>{this.output.textContent=JSON.stringify(motionDiagnostics(),null,2);};
      panel.insertBefore(closeup,this.output);panel.insertBefore(snapshot,this.output);
    }
    this.results={version,profile:compact?'mobile viewport':'desktop',physicalMobileTest:false};
    if(landscape){
      this.landscape=landscape;
      const wind=document.createElement('button');wind.textContent='Check visible tree movement';wind.onclick=()=>this.checkWind();panel.insertBefore(wind,this.output);
    }
  }
  save(){this.saved={position:this.camera.position.clone(),target:this.controls.target.clone()};this.controls.enabled=false;}
  restore(){this.camera.position.copy(this.saved.position);this.controls.target.copy(this.saved.target);this.controls.enabled=true;this.updateLandscape();this.invalidate();}
  startOrbit(record=false){
    if(this.active||this.checking)return;
    this.save();this.active=true;this.start=performance.now();this.frames=[];this.calls=[];this.triangles=[];this.previous=0;
    this.output.textContent='Warming shaders, then measuring a complete orbit…';
    this.recording=record;
    if(record){
      const stream=this.renderer.domElement.captureStream(30),chunks=[];
      this.recorder=new MediaRecorder(stream,{mimeType:'video/webm',videoBitsPerSecond:8000000});
      this.recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
      this.recorder.onstop=()=>{
        stream.getTracks().forEach(t=>t.stop());
        const link=document.createElement('a');link.textContent='Download orbit preview';link.download='new-komitas-orbit.webm';link.href=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));link.style.color='white';link.style.textDecoration='underline';this.output.after(link);
      };
      this.recorder.start();
    }
  }
  beforeFrame(now){
    if(!this.active)return false;
    const elapsed=now-this.start;
    if(elapsed>=16000){this.finishOrbit();return true;}
    const angle=Math.max(0,elapsed-2000)/14000*Math.PI*2+.55;
    this.controls.target.set(0,20,0);this.camera.position.set(Math.sin(angle)*420,280,Math.cos(angle)*420);
    return true;
  }
  afterRender(now){
    if(!this.active||now-this.start<2000)return;
    if(this.previous)this.frames.push(now-this.previous);
    this.previous=now;this.calls.push(this.renderer.info.render.calls);this.triangles.push(this.renderer.info.render.triangles);
    if(this.frames.length%30===0)this.output.textContent=`Orbit test running · ${Math.min(100,Math.round((now-this.start-2000)/140))}%`;
  }
  finishOrbit(){
    this.active=false;
    if(this.recording)this.recorder.stop();
    const sorted=[...this.frames].sort((a,b)=>a-b),at=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||0;
    const size=this.renderer.getDrawingBufferSize(new THREE.Vector2());
    this.results.orbit={frames:this.frames.length,medianFps:+(1000/at(.5)).toFixed(1),averageFps:+(1000*this.frames.length/this.frames.reduce((a,b)=>a+b,0)).toFixed(1),p95FrameMs:+at(.95).toFixed(2),p99FrameMs:+at(.99).toFixed(2),maxDrawCalls:Math.max(...this.calls),maxTriangles:Math.max(...this.triangles),drawingBuffer:[size.x,size.y],cssViewport:[this.renderer.domElement.clientWidth,this.renderer.domElement.clientHeight],reversedDepth:this.renderer.capabilities.reversedDepthBuffer,userAgent:navigator.userAgent,date:new Date().toISOString()};
    this.results.orbit.recording=this.recording;
    this.restore();this.output.textContent=JSON.stringify(this.results,null,2);
    this.onOrbitDone?.(this.results);
  }
  async checkStability(){
    if(this.active||this.checking)return;
    this.checking=true;this.save();this.output.textContent='Comparing 12 independently rendered stationary frames…';
    this.controls.update();this.updateLandscape();
    const target=new THREE.WebGLRenderTarget(512,288,{samples:4});
    let previous=null,changed=0,maxDelta=0;
    for(let frame=0;frame<12;frame++){
      await new Promise(requestAnimationFrame);
      this.renderer.setRenderTarget(target);this.renderer.render(this.scene,this.camera);
      const pixels=new Uint8Array(512*288*4);this.renderer.readRenderTargetPixels(target,0,0,512,288,pixels);
      if(previous)for(let i=0;i<pixels.length;i++)if(pixels[i]!==previous[i]){changed++;maxDelta=Math.max(maxDelta,Math.abs(pixels[i]-previous[i]));}
      previous=pixels;this.renderer.setRenderTarget(null);
    }
    target.dispose();this.results.stationary={frames:12,changedChannels:changed,maxChannelDelta:maxDelta,passed:changed===0,motionFrozenForComparison:true};
    this.checking=false;this.restore();this.output.textContent=JSON.stringify(this.results,null,2);
  }
  async checkWind(){
    if(this.active||this.checking)return;
    this.checking=true;this.save();this.controls.update();this.updateLandscape();
    const time=this.landscape.windTime.value,target=new THREE.WebGLRenderTarget(1024,576,{samples:4}),frames=[];
    try{
      for(const offset of [0,2]){
        this.landscape.animate(time+offset);await new Promise(requestAnimationFrame);
        this.renderer.setRenderTarget(target);this.renderer.render(this.scene,this.camera);
        const pixels=new Uint8Array(1024*576*4);this.renderer.readRenderTargetPixels(target,0,0,1024,576,pixels);frames.push(pixels);
      }
      let changed=0;
      for(let i=0;i<frames[0].length;i+=4)if(Math.max(...[0,1,2].map(c=>Math.abs(frames[0][i+c]-frames[1][i+c])))>12)changed++;
      this.results.windVisibility={secondsApart:2,resolution:[1024,576],changedPixels:changed,changedPercent:+(100*changed/(1024*576)).toFixed(2),cameraAndTrafficFrozen:true,passed:changed>2000};
    }finally{
      this.renderer.setRenderTarget(null);target.dispose();this.landscape.animate(time);this.checking=false;this.restore();this.output.textContent=JSON.stringify(this.results,null,2);
    }
  }
}
