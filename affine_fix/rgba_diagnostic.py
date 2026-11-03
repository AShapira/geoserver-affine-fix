"""Compare RGBA alpha handling across native/explicit styles and PNG encoders."""
import argparse
import json
from pathlib import Path
import rasterio
from rasterio.enums import ColorInterp, Resampling
from . import lab,probe
from .typed_suite import style,jobs_for,validity

class FormatSession:
    def __init__(self,session,format):self.session,self.format=session,format
    def get(self,url,**kwargs):
        kwargs['params']=dict(kwargs['params'],format=self.format)
        return self.session.get(url,**kwargs)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    a.root.mkdir(parents=True,exist_ok=False);a.root.chmod(0o700)
    result=json.loads((a.run/'result.json').read_text())
    entries=[dict(e,path=str(a.run/'typed-fixtures'/(e['name']+'.tif'))) for e in result['fixtures'] if e['kind']=='rgba']
    for e in entries:
        target=a.root/(e['name']+'.tif')
        with rasterio.open(e['path']) as src:
            profile=src.profile.copy();profile.update(photometric='RGB',alpha='non-premultiplied')
            data=src.read()
        with rasterio.open(target,'w',**profile) as dst:
            dst.write(data)
            if e['overviews']:dst.build_overviews([2,4,8,16],Resampling.nearest)
        with rasterio.open(target) as src:
            assert src.colorinterp[-1]==ColorInterp.alpha
        target.chmod(0o444);e['path']=str(target)
    rows=[]
    for variant in ('stock','both'):
        root=a.root/variant
        state=lab.up(argparse.Namespace(root=root,fixtures=a.run/'fixtures',engine='podman',connection=None,port=18126,pull=False,patch=a.run/'patch' if variant=='both' else None,extra_fixtures=[Path(e['path']) for e in entries]))
        try:
            probe.BASE=state['url'];probe.FIXTURE_ROOT=a.run/'fixtures';probe.SERVER_FIXTURE_DIR=state['server_fixture_dir']
            s=probe.session('admin',state['password_file']);probe.snapshot(root/'catalog',s);probe.publish(root/'catalog',s)
            probe.checked(s,'POST',f'/rest/workspaces/{probe.WS}/styles',params={'name':'rgba'},data=style('rgba'),headers={'Content-Type':'application/vnd.ogc.sld+xml'})
            for e in entries:
                name=e['name'];store=f'/rest/workspaces/{probe.WS}/coveragestores/{name}'
                probe.checked(s,'PUT',store+'/external.geotiff',params={'configure':'first','coverageName':name},data='/opt/affine-fixtures/'+name+'.tif',headers={'Content-Type':'text/plain'})
                probe.checked(s,'PUT',f'/rest/layers/{probe.WS}:{name}.json',json={'layer':{'defaultStyle':{'name':'rgba','workspace':probe.WS}}})
            explicit=style('rgba').replace('<RasterSymbolizer>', '<RasterSymbolizer><ChannelSelection>'+''.join(f'<{channel}Channel><SourceChannelName>{i}</SourceChannelName></{channel}Channel>' for channel,i in zip(('Red','Green','Blue'),(1,2,3)))+'</ChannelSelection>')
            probe.checked(s,'POST',f'/rest/workspaces/{probe.WS}/styles',params={'name':'rgba_explicit'},data=explicit,headers={'Content-Type':'application/vnd.ogc.sld+xml'})
            for selected in ('rgba','rgba_explicit'):
                for e in entries:
                    probe.checked(s,'PUT',f'/rest/layers/{probe.WS}:{e["name"]}.json',json={'layer':{'defaultStyle':{'name':selected,'workspace':probe.WS}}})
                for fmt in ('image/png','image/png8'):
                    for e in entries:
                        for j in jobs_for(e,True):
                            rows.append(dict(validity(FormatSession(s,fmt),e,j,a.root/selected/fmt.replace("/","_"),variant,1),format=fmt,style=selected))
                    probe.write_json(a.root/'result.json',rows)
        finally:
            lab.stop(state,root);lab.owned_container(state);lab.call(state['engine'],'rm',state['container_id'])
            (root/'lab.json').rename(root/'removed-lab.json')
    print('RGBA encoder diagnostic complete',flush=True)

if __name__=='__main__':main()
