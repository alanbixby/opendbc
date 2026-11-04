"""Reproduce final media from the research pickles; at most one parser at a time."""
import os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PY='/home/bxb/Develop/sunnypilot-ui/.venv/bin/python'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/home/bxb/Develop/sunnypilot-ui');env.pop('ARGV0',None)
JOBS=[
 ('pr2_corner_signed','102161de13e822d1/0000000d--f74a52a624/2','pr2_2',4,'pr2_2_empty','PR #2: signed corner radar','Research candidate - not published as tracks',['--corner-view','--range','45','--ref-dump',str(ROOT/'pr2_2_unsigned.pkl'),'--ref-label','unsigned','--extra-label','signed corner']),
 ('pr3_mdx_research','ad9840558640c31d/0000001a--d6cd4871c2/0','pr3_0',12,'pr3_0_empty','PR #3: Acura MDX research','Research candidate (unvalidated) - not published as tracks',['--extra-label','research candidate (unvalidated)']),
 ('pr7_510_detections','a6d25e95d936fdc4/000002ed--89d7944c52/4','pr7_4',16,'pr7_main','PR #7: Mobis 510 detection blocks','Research candidate - not published as tracks',['--extra-label','510 detections']),
 ('pr8_630_selected','ac27c9808ac91710/00000002--e0aab81e4d/2','pr8_2',15,'pr8_main','PR #8: 630 selected objects','Research candidate - not published as tracks',['--extra-label','630 selections'])]
if __name__=='__main__':
 for name,path,prefix,start,main,title,subtitle,opts in JOBS:
  subprocess.run([PY,str(ROOT/'render_research.py'),'--rlog',f'/home/bxb/Develop/radar-tracks/cache/{path}--rlog.zst','--qcam',str(ROOT/f'{prefix}--qcamera.ts'),'--dump',str(ROOT/f'{main}.pkl'),'--extra',str(ROOT/f'{prefix}_extra.pkl'),'--start',str(start),'--dur','8','--fps','7','--scale','1.3','--title',title,'--subtitle',subtitle,'--out',str(ROOT/f'{name}.gif'),*opts],cwd=ROOT.parent,env=env,check=True)

  if name == "pr2_corner_signed":
   subprocess.run(["ffmpeg","-v","error","-y","-i",str(ROOT/f"{name}.mp4"),"-vf",r"select=eq(n\,22)","-frames:v","1",str(ROOT/f"{name}.png")],check=True)
