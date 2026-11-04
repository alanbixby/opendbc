"""Download signed qcamera URLs without printing credentials; all outputs local."""
import json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ROUTES={'pr2':('102161de13e822d1','0000000d--f74a52a624',[2,6]),'pr3':('ad9840558640c31d','0000001a--d6cd4871c2',[0]),'pr7':('a6d25e95d936fdc4','000002ed--89d7944c52',[4]),'pr8':('ac27c9808ac91710','00000002--e0aab81e4d',[2])}
if __name__=='__main__':
 token=json.load(open('/home/bxb/.comma/auth.json'))['access_token']
 for key,(dongle,route,segs) in ROUTES.items():
  req=urllib.request.Request(f'https://api.commadotai.com/v1/route/{dongle}%7C{route}/files',headers={'Authorization':f'JWT {token}'})
  files=json.load(urllib.request.urlopen(req))
  for url in files['qcameras']:
   seg=int(urllib.parse.urlparse(url).path.split('/')[-2])
   if seg not in segs: continue
   out=ROOT/f'{key}_{seg}--qcamera.ts'
   if not out.exists(): urllib.request.urlretrieve(url,out)
   print(out.name,out.stat().st_size,flush=True)
