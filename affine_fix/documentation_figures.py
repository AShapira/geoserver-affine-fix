"""Capture real stock/current WMS images and plot independently checked comparisons."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from . import lab, probe, typed_suite as typed
from .reproduce import command


FIELDS = ('missing', 'spurious', 'alpha_mismatch', 'color_mismatch')


def image_path(root, variant, row, expected=False):
    stem = '_'.join(map(str, row['tile'])) + f'_g{row["gutter"]}'
    return root/'images'/variant/row['name']/(stem + ('-expected' if expected else '') + '.png')


def composite(rgba):
    """Use the same checkerboard for all panels; never modify measured RGBA arrays."""
    y, x = np.indices(rgba.shape[:2])
    background = np.where((x//16 + y//16) % 2, 195, 235)[..., None]
    alpha = rgba[..., 3:4].astype(float)/255
    return np.rint(rgba[..., :3]*alpha + background*(1-alpha)).astype(np.uint8)


def select(root, rows, kind, category):
    candidates = []
    current = {(r['name'], tuple(r['tile'])): r for r in rows if r['variant']=='current'}
    for row in rows:
        if row['variant'] != 'stock' or row['name'] != kind+'_r30_base' or row.get('error'):
            continue
        if any(current[row['name'], tuple(row['tile'])][k] for k in FIELDS):
            continue  # Passing illustrations only; every other capture stays in the known-issues evidence.
        expected = np.asarray(Image.open(image_path(root, 'stock', row, True)).convert('RGBA'))
        alpha = expected[..., 3]
        clear = int((alpha == 0).sum())
        partial = int(((alpha > 0) & (alpha < 255)).sum())
        visible = alpha > 0
        colors = len(np.unique(expected[..., :3][visible], axis=0))
        if category == 'color' and not (clear == 0 and colors >= 2 and row['tile'][0] >= 20):
            continue
        if category == 'rgba' and not (3000 < clear < 50000 and partial > 3000 and colors >= 3):
            continue
        if category == 'nodata' and not (3000 < clear < 50000 and colors >= 3 and row['tile'][0] <= 17):
            continue
        if category == 'edge' and not (10000 < clear < 55000 and row['tile'][0] >= 20):
            continue
        # Color panels demonstrate crop loss. Alpha panels show enough of each alpha state.
        score = sum(row[k] for k in FIELDS) if category in ('color', 'edge') else min(clear, 65536-clear) + partial
        candidates.append((score, row))
    if not candidates:
        raise ValueError(f'No suitable {kind}/{category} example; never substitute a fabricated image')
    return max(candidates, key=lambda x: x[0])[1]


def figure(root, output, filename, title, selections, rows):
    fig, axes = plt.subplots(len(selections), 3, figsize=(11.8, 4.0*len(selections)+.65),
                             layout='constrained', squeeze=False)
    fig.suptitle(title+'\nOfficial GeoServer 3.0.2 · same TIFF, request and gutter 1',
                 fontsize=15, fontweight='bold')
    evidence = []
    for index, (label, kind, category) in enumerate(selections):
        stock = select(root, rows, kind, category)
        fixed = next(r for r in rows if r['variant'] == 'current' and r['name'] == stock['name']
                     and r['tile'] == stock['tile'])
        panels = [('Official stock', image_path(root, 'stock', stock), stock),
                  ('Current fix', image_path(root, 'current', fixed), fixed),
                  ('Independent expected pixels', image_path(root, 'current', fixed, True), None)]
        for column, (heading, path, metrics) in enumerate(panels):
            rgba = np.asarray(Image.open(path).convert('RGBA'))
            ax = axes[index, column]
            ax.imshow(composite(rgba), interpolation='nearest')
            ax.set_title(heading, fontsize=12, weight='bold')
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_xlabel('Alpha errors: {:,} · Color errors: {:,}'.format(
                metrics['alpha_mismatch'], metrics['color_mismatch']) if metrics else 'Inverse source transform + nearest sample', fontsize=9)
            if column == 0: ax.set_ylabel(label, fontsize=11)
            for spine in ax.spines.values(): spine.set_color('#94a3b8')
        evidence.append(dict(label=label, stock=stock, current=fixed,
            response_sha256={v:probe.digest(image_path(root,v,r)) for v,r in [('stock',stock),('current',fixed)]},
            expected_sha256=probe.digest(image_path(root,'current',fixed,True))))
    fig.supxlabel('Checkerboard = transparent; faint checkerboard through color = partial alpha. Synthetic data, not photographs.', fontsize=10)
    destination = output/filename
    fig.savefig(destination, dpi=155, facecolor='white')
    plt.close(fig)
    return dict(file=filename, sha256=probe.digest(destination), panels=evidence)


def publish(root, output):
    metadata=json.loads((root/'capture.json').read_text())
    rows=json.loads((root/'checks.json').read_text())
    baseline={(r['name'],tuple(r['tile'])):r for r in rows if r['variant']=='baseline'}
    known=[]
    for row in rows:
        if row.get('error'): raise ValueError('Invalid image response: '+repr(row))
        a=np.asarray(Image.open(image_path(root,row['variant'],row)).convert('RGBA'))
        expected=np.asarray(Image.open(image_path(root,row['variant'],row,True)).convert('RGBA'))
        visible=expected[...,3]>0
        measured=dict(alpha_mismatch=int((np.abs(a[...,3].astype(int)-expected[...,3].astype(int))>1).sum()),
            color_mismatch=int((np.any(np.abs(a[...,:3].astype(int)-expected[...,:3].astype(int))>2,axis=2)&visible).sum()),
            missing=int(((a[...,3]==0)&visible).sum()),spurious=int(((a[...,3]>0)&~visible).sum()))
        if any(row[k]!=measured[k] for k in FIELDS): raise ValueError('Capture measurements changed')
        if row['variant']=='current' and any(measured.values()):
            before=baseline.get((row['name'],tuple(row['tile'])))
            if not before: raise ValueError('A failed current capture requires a previous-candidate comparison')
            old=np.asarray(Image.open(image_path(root,'baseline',before)).convert('RGBA'))
            visible=(a[...,3]>0)|(old[...,3]>0)
            if not (np.array_equal(a[...,3],old[...,3]) and np.array_equal(a[visible,:3],old[visible,:3])):
                raise ValueError('New difference from the previous candidate: '+repr(row))
            known.append(dict(row,identical_to_previous_candidate=True))
    figures = [figure(root,output,'rgb-multiband.png','Rotated color rasters: keep valid source pixels',
                      [('RGB · three channels','rgb','color'),('UInt16 · four bands, display 4/2/1','multispectral','color')],rows),
               figure(root,output,'rgba-transparency.png','Preserve transparent pixels and the raster footprint',
                      [('RGBA · hole + alpha 128 (~50%)','rgba','rgba'),('RGB · transparent outside footprint','rgb','edge')],rows),
               figure(root,output,'nodata-transparency.png','Elevation: preserve NoData holes and valid zero values',
                      [('Float32 · NoData = −9999','dem','nodata'),('Float32 · NoData = NaN','dem_nan','nodata')],rows)]
    report=dict(metadata,checks=rows,figures=figures,known_downsampling_mismatches=known)
    probe.write_json(output/'raster-comparisons.json',report)
    print('Published',len(figures),'figures from',len(rows),'fresh image checks;',len(known),'unchanged boundary cases recorded',flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('docs/assets'))
    p.add_argument('--patch', type=Path, help='Reuse an already verified build directory')
    p.add_argument('--baseline-patch', type=Path, help='Previous correctness-validated candidate for additional cases')
    p.add_argument('--baseline-lock', type=Path)
    p.add_argument('--render-only', action='store_true', help='Replot retained captures and recheck their measurements')
    p.add_argument('--engine', default='podman')
    p.add_argument('--connection')
    p.add_argument('--port', type=int, default=18176)
    p.add_argument('--pull', action='store_true')
    a = p.parse_args()
    if bool(a.baseline_patch) != bool(a.baseline_lock): p.error('Use both baseline options together')
    a.output.mkdir(parents=True, exist_ok=True)
    if a.render_only:
        publish(a.root,a.output)
        return
    a.root = a.root.resolve(); a.root.mkdir(parents=True, exist_ok=False); a.root.chmod(0o700)
    lock = lab.load_lock()
    probe.FIXTURE_ROOT = None
    probe.fixtures(a.root/'fixtures')
    entries = typed.fixtures(a.root/'typed-fixtures')
    patch = a.patch.resolve() if a.patch else a.root/'patch'
    if a.patch:
        lab.patch_payload(patch, lock)
        build = json.loads((patch/'build.json').read_text())
        if build.get('source_sha256') != lock['source_sha256']:
            raise ValueError('Reused image build must match the current locked sources')
    else:
        flags = ['--engine', a.engine, '--output', patch]
        if a.connection: flags += ['--connection', a.connection]
        if a.pull: flags += ['--pull']
        command(a.root/'build.log', 'affine_fix.build', *flags)
    selected = [e for e in entries if e['angle'] == 30 and not e['overviews']]
    rows = []
    for variant in (('stock','baseline','current') if a.baseline_patch else ('stock','current')):
        root = a.root/variant
        state = lab.up(argparse.Namespace(root=root, fixtures=a.root/'fixtures', engine=a.engine,
            connection=a.connection, port=a.port, pull=a.pull,
            patch=patch if variant=='current' else a.baseline_patch if variant=='baseline' else None,
            patch_lock=a.baseline_lock if variant=='baseline' else None,
            components='both', extra_fixtures=[Path(e['path']) for e in selected]))
        try:
            probe.BASE=state['url']; probe.FIXTURE_ROOT=a.root/'fixtures'; probe.SERVER_FIXTURE_DIR=state['server_fixture_dir']
            s = probe.session('admin', state['password_file'])
            probe.snapshot(root/'catalog',s); probe.publish(root/'catalog',s)
            for e in selected:
                kind,name=e['kind'],e['name']
                probe.checked(s,'POST',f'/rest/workspaces/{probe.WS}/styles',params={'name':kind},
                              data=typed.style(kind),headers={'Content-Type':'application/vnd.ogc.sld+xml'})
                probe.checked(s,'PUT',f'/rest/workspaces/{probe.WS}/coveragestores/{name}/external.geotiff',
                    params={'configure':'first','coverageName':name},data='/opt/affine-fixtures/'+name+'.tif',
                    headers={'Content-Type':'text/plain'})
                probe.checked(s,'PUT',f'/rest/layers/{probe.WS}:{name}.json',
                    json={'layer':{'defaultStyle':{'name':kind,'workspace':probe.WS}}})
                tiles={tuple(j['tile']) for j in typed.jobs_for(e, True)}
                for zoom in (15,16,17):
                    for x,y in ((.5,.5),(.6,.5),(.67,.5),(.5,.6)):
                        tiles.add(probe.tile_at(zoom,*probe.world(e['gt'],x*typed.SIZE,y*typed.SIZE)))
                for tile in sorted(tiles):
                    rows.append(typed.validity(s,e,dict(name=name,tile=list(tile)),a.root,variant,1,save_images=True))
            probe.write_json(a.root/'checks.json',rows)
        finally:
            lab.stop(state,root); lab.owned_container(state); lab.call(state['engine'],'rm',state['container_id'])
            (root/'lab.json').rename(root/'removed-lab.json')
    assert all(probe.digest(Path(e['path'])) == e['sha256'] for e in entries)
    report=dict(checked_utc=datetime.now(timezone.utc).isoformat(),runtime=lock,
                build=json.loads((patch/'build.json').read_text()),gutter=1,
                baseline_runtime=json.loads(a.baseline_lock.read_text()) if a.baseline_lock else None,
                baseline_build=json.loads((a.baseline_patch/'build.json').read_text()) if a.baseline_patch else None,
                fixtures=[{k:v for k,v in e.items() if k!='path'} for e in selected],
                fixtures_unchanged=True,servers_removed=True)
    probe.write_json(a.root/'capture.json',report)
    publish(a.root,a.output)


if __name__ == '__main__': main()
