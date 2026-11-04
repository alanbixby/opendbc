"""Replay branch-generated research DBCs; emit renderer pickles, never production tracks.
Use PYTHONDONTWRITEBYTECODE=1 and the matching read-only branch first on PYTHONPATH.
"""
import argparse, pickle, subprocess, json
from pathlib import Path
from openpilot.tools.lib.logreader import LogReader
from opendbc.can import CANParser
from opendbc import get_generated_dbcs
ROOT=Path(__file__).resolve().parent
REPO='/home/bxb/Develop/radar-tracks/opendbc'
SPECS={
 'pr2':('radar-corner-signed-long-dist','hyundai','hyundai_corner_radar_240_28f',0,24,list(range(0x241,0x250))+list(range(0x279,0x288))),
 'pr3':('radar-acura-mdx-4g-v2','honda','acura_mdx_4g_objects_research',1,64,list(range(0x62,0x81,2))),
 'pr7':('radar-510-630-blocks','hyundai','hyundai_radar_detections_510_51f',1,64,list(range(0x510,0x520))),
 'pr8':('radar-630-selected-objects','hyundai','hyundai_selected_objects_630_63d',1,8,list(range(0x630,0x63e,2)))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('kind',choices=SPECS);ap.add_argument('rlog');ap.add_argument('--prefix',required=True);a=ap.parse_args()
 branch,brand,dbc,bus,size,addrs=SPECS[a.kind]
 snapshot=ROOT/'generators'/f'{dbc}.py'
 source=snapshot.read_text() if snapshot.exists() else subprocess.check_output(['git','-C',REPO,'show',f'origin/{branch}:opendbc/dbc/generator/{brand}/{dbc}.py'],text=True)
 ns={};exec(compile(source,dbc,'exec'),ns)
 get_generated_dbcs().update({k.removesuffix('.dbc'):v for k,v in ns['generate']().items()})
 from opendbc.can.dbc import DBC
 names={addr:DBC(dbc).addr_to_msg[addr].name for addr in addrs}
 cp=CANParser(dbc,[(names[x],20 if a.kind!='pr3' else 15) for x in addrs],bus)
 states={};outputs=[];refs=[];empty=[];models=[];enc={};platform='ACURA_MDX_4G_MMR';last=0;crossings=[];previous={}
 for m in LogReader(a.rlog):
  w=m.which();t=m.logMonoTime
  if w=='carParams': platform=m.carParams.carFingerprint
  elif w=='qNarrowRoadEncodeIdx': enc[int(m.qNarrowRoadEncodeIdx.segmentId)]=int(m.qNarrowRoadEncodeIdx.timestampSof)
  elif w=='modelV2':
   ld=m.modelV2.leadsV3[0];models.append((t,ld.prob,ld.x[0]-1.52,-ld.y[0]))
  elif w=='can':
   msgs=[(c.address,bytes(c.dat),c.src) for c in m.can if c.src==bus and c.address in names and len(c.dat)==size]
   if not msgs: continue
   updated=cp.update([(t,msgs)])
   for addr in updated:
    v=cp.vl[names[addr]];pts=[]
    if a.kind=='pr2':
     x=v['LONG_DIST'];y=v['LAT_DIST'];speed=v['REL_SPEED']
     if abs(x-204.7)>0.001:
      pts=[(addr,x,y,speed,0,addr,bus)]
      old=previous.get(addr)
      if old and 0 < old[1] < 2 and -2 < x < 0 and t-old[0]<0.15e9:crossings.append((t,addr,old[1],x,y))
      previous[addr]=(t,x)
    elif a.kind=='pr3':
     if v['OBJECT_ID_RAW']:
      pts=[(addr*256+int(v['OBJECT_ID_RAW']),v['POSITION_X_LOW_12_RAW']*0.04255+0.714,v['POSITION_Y_LOW_13_RAW']*0.01,0.,0,addr,bus)]
    elif a.kind=='pr7':
     for i in range(4):
      p=f'DETECTION_{i}_'
      if v[p+'VALID']:pts.append((addr*4+i,v[p+'LONG_POSITION_CANDIDATE'],-v[p+'LAT_POSITION_CANDIDATE'],v[p+'DOPPLER_CANDIDATE'],0,addr,bus))
    else:
     if 0<v['DISTANCE_CANDIDATE']<199.99:pts=[(addr,v['DISTANCE_CANDIDATE'],-v['LAT_POSITION_CANDIDATE'],v['REL_SPEED_CANDIDATE'],0,addr,bus)]
    states[addr]=(t,pts)
   if t-last<0.045e9:continue
   last=t;pts=[p for ts,ps in states.values() if t-ts<0.2e9 for p in ps]
   outputs.append((t,pts,[]));empty.append((t,[],[]))
   if a.kind=='pr2':refs.append((t,[(p[0],p[1] if p[1]>=0 else p[1]+409.6,*p[2:]) for p in pts],[]))
 for suffix,out in [('extra',outputs),('empty',empty),('unsigned',refs)]:
  if out:pickle.dump({'platform':platform,'outputs':out},open(a.prefix+'_'+suffix+'.pkl','wb'))
 t0=enc[min(enc)] if enc else outputs[0][0]
 summary={'platform':platform,'first_frame_ns':t0,'crossings':[((t-t0)/1e9,hex(addr),x0,x1,y) for t,addr,x0,x1,y in crossings], 'models':[((t-t0)/1e9,p,x,y) for t,p,x,y in models][::20]}
 Path(a.prefix+'_summary.json').write_text(json.dumps(summary,indent=2));print(a.prefix,len(outputs),'crossings',len(crossings),flush=True)
if __name__=='__main__':main()
