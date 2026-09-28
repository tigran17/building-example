/** Constant-distance sampling of prevalidated right-hand lanes, in meters.
 *  Samples are [x, z, s, shade]; shade (sun visibility, precomputed in Blender) is optional. */
export function sampleLane(lane,distance){
  const s=((distance%lane.length)+lane.length)%lane.length,rows=lane.samples;
  let lo=0,hi=rows.length-1;
  while(hi-lo>1){const mid=(lo+hi)>>1;if(rows[mid][2]<=s)lo=mid;else hi=mid;}
  const a=rows[lo],b=rows[hi],t=(s-a[2])/Math.max(.00001,b[2]-a[2]);
  const dx=b[0]-a[0],dz=b[1]-a[1];
  const edge=Math.min(1,Math.max(0,Math.min(s,lane.length-s)/lane.fadeMeters));
  const shade=a.length>3?a[3]+(b[3]-a[3])*t:1;
  return {x:a[0]+dx*t,z:a[1]+dz*t,angle:Math.atan2(-dx,-dz),distance:s,fade:edge*edge*(3-2*edge),shade};
}
