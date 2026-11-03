"""Validity and performance of RGB, alpha, UInt16 and Float32 GeoTIFFs."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.transform import Affine

from . import lab, probe, benchmark, benchmark_metrics as bm
from .reproduce import command

KINDS = ('rgb', 'rgba', 'multispectral', 'dem', 'dem_nan')
SIZE = 2048
COLORS = np.array([[40, 80, 160], [80, 160, 40], [160, 40, 80], [200, 150, 60]], dtype=np.uint8)


class TypedRunner(benchmark.Runner):
    def block(self, variant, jobs, **kwargs):
        if kwargs.get('profile') == 'gwc-hit':
            # Retain timed failures even if a broken renderer cannot prime a tile.
            self.perform(variant, jobs, 'gwc-hit', kwargs['gutter'], kwargs['concurrency'])
            kwargs['prepare'] = False
        return super().block(variant, jobs, **kwargs)


def samples(kind, x, y):
    x, y = np.broadcast_arrays(x, y)
    category = ((x // 128) + 2 * (y // 128)) % 4
    rgb = COLORS[category]
    alpha = np.full(x.shape, 255, dtype=np.uint8)
    hole = ((x - 1024)**2 + (y - 1024)**2 < 180**2) | (x < 64) | (y < 64)
    if kind == 'rgba':
        alpha[hole] = 0
        alpha[(x >= 1300) & (x < 1550)] = 128
    if kind.startswith('dem'):
        alpha[hole] = 0
        data = np.array([-100, 0, 100, 1000], dtype=np.float32)[category]
        data[hole] = np.nan if kind == 'dem_nan' else -9999
        return data[None], np.concatenate((rgb, alpha[..., None]), axis=-1)
    if kind == 'multispectral':
        # Style selects 4,2,1; band 3 is deliberately unrelated to the output.
        data = np.stack((rgb[..., 2], rgb[..., 1], np.full(x.shape, 17), rgb[..., 0])).astype(np.uint16) * 257
    else:
        data = np.moveaxis(rgb, -1, 0)
        if kind == 'rgba': data = np.concatenate((data, alpha[None]))
    return data, np.concatenate((rgb, alpha[..., None]), axis=-1)


def fixtures(root, kinds=KINDS):
    root.mkdir()
    y, x = np.indices((SIZE, SIZE))
    entries = []
    for kind in kinds:
        data, _ = samples(kind, x, y)
        for angle in (0, 30):
            for overview in (False, True):
                name = f'{kind}_r{angle}_' + ('ovr' if overview else 'base')
                path = root / (name + '.tif')
                gt = probe.affine(angle, size=SIZE)
                options = dict(driver='GTiff', width=SIZE, height=SIZE, count=len(data), dtype=data.dtype,
                               crs='EPSG:3857', transform=Affine.from_gdal(*gt), tiled=True,
                               blockxsize=256, blockysize=256, compress='deflate')
                if kind.startswith('dem'): options['nodata'] = np.nan if kind == 'dem_nan' else -9999
                if kind in ('rgb', 'rgba'): options['photometric'] = 'RGB'
                if kind == 'rgba': options['alpha'] = 'non-premultiplied'
                with rasterio.open(path, 'w', **options) as ds:
                    ds.write(data)
                    if kind == 'rgba': ds.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
                    if kind == 'multispectral': ds.colorinterp = (ColorInterp.undefined,) * 4
                    if overview: ds.build_overviews([2, 4, 8, 16], Resampling.nearest)
                path.chmod(0o444)
                with rasterio.open(path) as check:
                    if kind == 'rgba' and check.colorinterp[-1] != ColorInterp.alpha:
                        raise RuntimeError('RGBA fixture did not retain its alpha tag')
                entries.append(dict(name=name, kind=kind, angle=angle, overviews=overview,
                                    gt=gt, size=SIZE, path=str(path), sha256=probe.digest(path)))
    return entries


def style(kind):
    if kind.startswith('dem'):
        content = '<ChannelSelection><GrayChannel><SourceChannelName>1</SourceChannelName></GrayChannel></ChannelSelection><ColorMap type="values">'
        for value, rgb in zip((-100, 0, 100, 1000), COLORS):
            color = '#' + ''.join(f'{v:02x}' for v in rgb)
            content += f'<ColorMapEntry quantity="{value}" color="{color}"/>'
        content += '</ColorMap>'
    elif kind == 'multispectral':
        content = '<ChannelSelection>'
        for channel, band in zip(('Red', 'Green', 'Blue'), (4, 2, 1)):
            content += f'<{channel}Channel><SourceChannelName>{band}</SourceChannelName><ContrastEnhancement><Normalize><VendorOption name="algorithm">StretchToMinimumMaximum</VendorOption><VendorOption name="minValue">0</VendorOption><VendorOption name="maxValue">65535</VendorOption></Normalize></ContrastEnhancement></{channel}Channel>'
        content += '</ChannelSelection>'
    else:
        content = ''  # Native RGB/RGBA interpretation, including intrinsic alpha.
    return f'<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld"><NamedLayer><Name>{kind}</Name><UserStyle><FeatureTypeStyle><Rule><RasterSymbolizer>{content}</RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>'


def jobs_for(item, validity=False):
    points = [(.25,.25),(.4,.6),(.5,.5),(.67,.5),(.73,.6),(.85,.85)]
    if validity: points += [(0,.5),(1,.5),(.5,0),(.5,1),(.03,.3)]
    zooms = (20,22,24) if validity else (16,18,20,22,24)
    return [dict(name=item['name'], tile=list(t)) for t in sorted({probe.tile_at(z,*probe.world(item['gt'],px*SIZE,py*SIZE)) for z in zooms for px,py in points})]


def validity(session, item, job, root, variant, gutter):
    bbox = probe.tile(*job['tile']); res = (bbox[2]-bbox[0])/256
    expanded = [bbox[0]-gutter*res,bbox[1]-gutter*res,bbox[2]+gutter*res,bbox[3]+gutter*res]
    params = probe.wms(item['name'],expanded,width=256+2*gutter,height=256+2*gutter)
    params['transparent'] = 'true'
    response = session.get(probe.BASE+'/wms',params=params,timeout=120)
    row = dict(name=item['name'],tile=job['tile'],variant=variant,gutter=gutter)
    if not response.ok or not response.headers.get('Content-Type','').startswith('image/png'):
        return dict(row,error='invalid_image_response')
    image = Image.open(io.BytesIO(response.content)).convert('RGBA')
    image.load()
    if image.size != (256+2*gutter,)*2: return dict(row,error='wrong_dimensions')
    image = image.crop((gutter,gutter,gutter+256,gutter+256))
    actual = np.asarray(image)
    x=bbox[0]+(np.arange(256)+.5)*res; y=bbox[3]-(np.arange(256)+.5)*res
    col, rowpix = probe.pixel_coordinates(item['gt'],x[None,:],y[:,None])
    ci,ri=np.floor(col).astype(int),np.floor(rowpix).astype(int)
    inside=(ci>=0)&(ci<SIZE)&(ri>=0)&(ri<SIZE)
    _, expected=samples(item['kind'],ci,ri)
    expected[~inside,3]=0
    alpha_error=np.abs(actual[...,3].astype(int)-expected[...,3].astype(int))>1
    visible=expected[...,3]>0
    color_error=np.any(np.abs(actual[...,:3].astype(int)-expected[...,:3].astype(int))>2,axis=2)&visible
    result=dict(row,alpha_mismatch=int(alpha_error.sum()),color_mismatch=int(color_error.sum()),
                missing=int(((actual[...,3]==0)&visible).sum()),
                spurious=int(((actual[...,3]>0)&(expected[...,3]==0)).sum()))
    if result['alpha_mismatch'] or result['color_mismatch']:
        directory=root/'images'/variant/item['name'];directory.mkdir(parents=True,exist_ok=True)
        stem='_'.join(map(str,job['tile']))+f'_g{gutter}'
        image.save(directory/(stem+'.png'));Image.fromarray(expected).save(directory/(stem+'-expected.png'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.runs/typed-3.0.2'))
    parser.add_argument('--replicates',type=int,default=3)
    parser.add_argument('--quality-only',action='store_true',help='Run one validity replicate without performance timing')
    parser.add_argument('--variants',nargs='+',choices=('stock','both'),default=['stock','both'])
    parser.add_argument('--patch',type=Path,help='Reuse a previously built candidate directory')
    parser.add_argument('--kinds',nargs='+',choices=KINDS,default=list(KINDS))
    args=parser.parse_args();args.root=args.root.resolve();args.root.mkdir(parents=True,exist_ok=False);args.root.chmod(0o700)
    probe.FIXTURE_ROOT=None
    probe.fixtures(args.root/'fixtures')
    entries=fixtures(args.root/'typed-fixtures',args.kinds)
    if args.quality_only: args.replicates=1
    patch=args.patch.resolve() if args.patch else args.root/'patch'
    if not args.patch: command(args.root/'build.log','affine_fix.build','--output',patch)
    jobs=[j for e in entries for j in jobs_for(e)]
    runner=TypedRunner(args,entries,{'typed':jobs})
    quality=[];started=datetime.now(timezone.utc).isoformat();complete=False
    try:
        for rep in range(args.replicates):
            runner.current_replicate=rep
            for variant in [v for v in (('stock','both') if rep%2==0 else ('both','stock')) if v in args.variants]:
                root=args.root/f'replicate-{rep}'/variant
                state=lab.up(argparse.Namespace(root=root,fixtures=args.root/'fixtures',engine='podman',connection=None,port=18116+(variant=='both'),pull=False,patch=patch if variant=='both' else None,components='both',extra_fixtures=[Path(e['path']) for e in entries]))
                runner.states[variant]=state;runner.cgroups[variant]=bm.cgroup_path(state)
                s=probe.session('admin',state['password_file']);runner.sessions[variant]=s;runner.select(variant)
                probe.snapshot(root/'catalog',s);probe.publish(root/'catalog',s)
                for kind in KINDS:
                    probe.checked(s,'POST',f'/rest/workspaces/{probe.WS}/styles',params={'name':kind},data=style(kind),headers={'Content-Type':'application/vnd.ogc.sld+xml'})
                for e in entries:
                    name=e['name'];store=f'/rest/workspaces/{probe.WS}/coveragestores/{name}'
                    probe.checked(s,'PUT',store+'/external.geotiff',params={'configure':'first','coverageName':name},data='/opt/affine-fixtures/'+name+'.tif',headers={'Content-Type':'text/plain'})
                    probe.checked(s,'PUT',f'/rest/layers/{probe.WS}:{name}.json',json={'layer':{'defaultStyle':{'name':e['kind'],'workspace':probe.WS}}})
                    probe.cache_config(s,name,1,1)
                runner.servers.append(dict(replicate=rep,variant=variant,image=state['image'],versions=json.loads((root/'version.json').read_text())))
                if rep==0:
                    for e in entries:
                        for gutter in (0,1):
                            quality.extend(validity(s,e,j,args.root,variant,gutter) for j in jobs_for(e,True))
                    probe.write_json(args.root/'quality.json',quality)
                if not args.quality_only:
                    for _ in range(2): runner.perform(variant,jobs,'wms',1,6)
            if args.quality_only:
                runner.close_servers()
                continue
            for round in range(3):
                shuffled=list(jobs);random.Random(rep*100+round).shuffle(shuffled)
                for concurrency in (1,6):
                    for profile in ('wms','gwc-miss','gwc-hit'):
                        for variant in [v for v in (('stock','both') if (rep+round+concurrency)%2 else ('both','stock')) if v in args.variants]:
                            runner.block(variant,shuffled,replicate=rep,round=round,suite='typed',profile=profile,gutter=1,concurrency=concurrency)
            runner.close_servers()
        assert all(probe.digest(Path(e['path']))==e['sha256'] for e in entries)
        complete=True
    finally:
        for pool in runner.pools.values():pool.shutdown()
        if runner.states:runner.close_servers()
        probe.write_json(args.root/'result.json',dict(complete=complete,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),runtime=lab.load_lock(),quality_only=args.quality_only,patch_build=json.loads((patch/'build.json').read_text()),environment=bm.environment(),servers=runner.servers,fixtures=[{k:v for k,v in e.items() if k!='path'} for e in entries],quality=quality,blocks=runner.blocks))
    print('COMPLETE',sum(b['summary']['requests'] for b in runner.blocks),'requests',flush=True)


if __name__=='__main__':main()
