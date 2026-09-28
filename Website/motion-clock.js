/** Simulation clock: no jump after hidden tabs, pauses, or a delayed frame. */
export class MotionClock {
  constructor(paused=false){this.paused=paused;this.time=0;this.previous=null;}
  tick(now,hidden=false,frozen=false){
    const dt=this.previous===null?0:Math.min(.05,Math.max(0,(now-this.previous)/1000));
    this.previous=now;
    if(this.paused||hidden||frozen)return false;
    this.time+=dt;return dt>0;
  }
  setPaused(paused){this.paused=paused;this.previous=null;}
}
