"""Plot actual transparency failures against the independent oracle."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from affine_fix import probe
import argparse
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('docs/typed-raster-tests'));args=p.parse_args()
root=args.run;q=json.loads((root/'quality.json').read_text())
fig,axes=plt.subplots(2,3,figsize=(11,7),layout='constrained')
for row,name in enumerate(['rgb_r30_base','dem_r30_base']):
 candidates=[r for r in q if r['name']==name and r['gutter']==1 and r['variant']=='both' and r.get('spurious')]
 if row==1:
  candidates=[r for r in candidates if all(500<c<1500 and 500<y<1500 for c,y in [probe.pixel_coordinates(probe.affine(30,size=2048),(probe.tile(*r['tile'])[0]+probe.tile(*r['tile'])[2])/2,(probe.tile(*r['tile'])[1]+probe.tile(*r['tile'])[3])/2)])]
 r=max(candidates,key=lambda r:r['spurious']);stem='_'.join(map(str,r['tile']))+'_g1'
 paths=[root/'images'/v/name/(stem+'.png') for v in ['stock','both']]+[root/'images/both'/name/(stem+'-expected.png')]
 yy,xx=np.indices((256,256));bg=np.where((xx//16+yy//16)%2,180,230)[...,None]
 for col,(path,label) in enumerate(zip(paths,['Stock','Both corrections','Expected'])):
  a=np.asarray(Image.open(path).convert('RGBA')).astype(float);alpha=a[...,3:]/255
  composed=(a[...,:3]*alpha+bg*(1-alpha)).astype(np.uint8)
  axes[row,col].imshow(composed);axes[row,col].set_title(label);axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
 axes[row,0].set_ylabel('RGB footprint edge' if row==0 else 'Elevation NoData hole')
fig.suptitle('Transparent-output failures: checkerboard means transparency',weight='bold')
args.output.mkdir(parents=True,exist_ok=True)
fig.savefig(args.output/'transparency.png',dpi=140)
