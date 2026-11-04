"""Reproduce all pickles sequentially using existing branch checkouts, without writes there."""
import os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PY='/home/bxb/Develop/sunnypilot-ui/.venv/bin/python'
JOBS=[('pr2','corner-signed','102161de13e822d1/0000000d--f74a52a624/2','pr2_2'),('pr3','mdx','ad9840558640c31d/0000001a--d6cd4871c2/0','pr3_0'),('pr7','b510','a6d25e95d936fdc4/000002ed--89d7944c52/4','pr7_4'),('pr8','audit-fix','ac27c9808ac91710/00000002--e0aab81e4d/2','pr8_2')]
if __name__=='__main__':
 for kind,branch,path,prefix in JOBS:
  env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=f'/home/bxb/Develop/radar-tracks/review/{branch}:/home/bxb/Develop/sunnypilot-ui');env.pop('ARGV0',None)
  subprocess.run([PY,str(ROOT/'decode_candidates.py'),kind,f'/home/bxb/Develop/radar-tracks/cache/{path}--rlog.zst','--prefix',str(ROOT/prefix)],env=env,cwd=ROOT.parent,check=True)
 for prefix,path in [('pr7_main',JOBS[2][2]),('pr8_main',JOBS[3][2])]:
  subprocess.run([PY,str(ROOT.parent/'dump_radar.py'),f'/home/bxb/Develop/radar-tracks/cache/{path}--rlog.zst','--out',str(ROOT/f'{prefix}.pkl')],env=env,cwd=ROOT.parent,check=True)
