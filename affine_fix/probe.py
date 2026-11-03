"""Immutable affine GeoTIFF fixtures and evidence-driven GeoServer probes.

Runs locally or in an isolated lab with explicit paths and credentials.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import io
import json
import math
import struct
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import requests

WS = 'affine_probe'
BASE = 'http://127.0.0.1:18096/geoserver'
FIXTURE_ROOT = None
SERVER_FIXTURE_DIR = None
HALF = 20037508.342789244
GRID = 'affine_3857'


class RenderFailure(RuntimeError):
    def __init__(self, response):
        self.url = response.url
        self.status = response.status_code
        self.body = response.content
        super().__init__(f'HTTP {response.status_code}: {response.text[:1000]}')


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def affine(angle, size=4096, shear=False, scales=(1, 1)):
    r = math.radians(angle)
    a, b = math.cos(r) * scales[0], math.sin(r) * scales[1]
    d, e = math.sin(r) * scales[0], -math.cos(r) * scales[1]
    if shear:
        b += .35
    return [3900000 - size * (a + b) / 2, a, b,
            3800000 - size * (d + e) / 2, d, e]


def world(gt, col, row):
    return gt[0] + gt[1] * col + gt[2] * row, gt[3] + gt[4] * col + gt[5] * row


def pixel_coordinates(gt, x, y):
    det = gt[1] * gt[5] - gt[2] * gt[4]
    if abs(det) < 1e-15:
        raise ValueError('Singular affine transform')
    dx, dy = np.asarray(x) - gt[0], np.asarray(y) - gt[3]
    return (gt[5] * dx - gt[2] * dy) / det, (-gt[4] * dx + gt[1] * dy) / det


def expected(source, gt, bbox, width=256, height=256):
    x = bbox[0] + (np.arange(width) + .5) * (bbox[2] - bbox[0]) / width
    y = bbox[3] - (np.arange(height) + .5) * (bbox[3] - bbox[1]) / height
    cols, rows = pixel_coordinates(gt, x[None, :], y[:, None])
    ci, ri = np.floor(cols).astype(int), np.floor(rows).astype(int)
    valid = (ci >= 0) & (ri >= 0) & (ci < source.shape[1]) & (ri < source.shape[0])
    result = np.full((height, width), 255, dtype=source.dtype)
    result[valid] = source[ri[valid], ci[valid]]
    # Do not erase a border around the footprint: narrow real gaps must remain detectable.
    return result, valid


def metrics(image, reference, valid):
    a = np.array(image.convert('RGBA'))
    rgb = a[:, :, :3].astype(float)
    blank = (a[:, :, 3] == 0) | np.all(rgb >= 254, axis=2) | np.all(rgb <= 1, axis=2)
    holes = blank & valid
    gray = rgb.mean(axis=2)
    errors = np.abs(gray - reference.astype(float))
    good = valid & ~blank
    result = {'valid_pixels': int(valid.sum()), 'missing_pixels': int(holes.sum()),
              'missing_fraction': float(holes.sum() / max(1, valid.sum())),
              'mae_valid_nonblank': float(errors[good].mean()) if good.any() else None,
              'exact_fraction_nonblank': float((errors[good] == 0).mean()) if good.any() else None}
    return result, holes


def pattern(size):
    y, x = np.indices((size, size), dtype=np.uint32)
    out = np.where((x // 4 + y // 4) % 2, 208, 48).astype(np.uint8)
    ramp = 32 + (x * 191 // max(1, size - 1))
    out[(y >= size // 4) & (y < size // 2)] = np.broadcast_to(ramp, out.shape)[(y >= size // 4) & (y < size // 2)]
    texture = 32 + ((x * 73856093 ^ y * 19349663) % 192)
    out[(y >= size // 2) & (y < 3 * size // 4)] = texture[(y >= size // 2) & (y < 3 * size // 4)]
    lines = np.where((x % 16 < 2) | (y % 32 < 2) | (x > y), 208, 48)
    out[y >= 3 * size // 4] = lines[y >= 3 * size // 4]
    return out


def fixtures(root, size=4096):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    root = Path(root)
    if size < 16 or size > 4096:
        raise ValueError('Fixture size must be between 16 and 4096')
    manifest_path = root / 'fixtures.json'
    if manifest_path.exists():
        entries = verify(root)
        if any(item['size'] != size for item in entries):
            raise ValueError('Existing fixtures have a different size; use another directory')
        return
    directory = root / 'fixtures'
    directory.mkdir(parents=True, exist_ok=True)
    source = pattern(size)
    entries = []
    for angle, shear in [(0, False), (15, False), (30, False), (45, False), (75, False), (-30, False), (30, True)]:
        for overview in (False, True):
            name = ('shear' if shear else 'rot' + str(angle).replace('-', 'm')) + ('_ovr' if overview else '_base')
            path = directory / (name + '.tif')
            if path.exists():
                raise RuntimeError(f'Unmanifested fixture exists; do not overwrite: {path}')
            gt = affine(angle, size=size, shear=shear)
            with rasterio.open(path, 'w', driver='GTiff', width=size, height=size,
                    count=1, dtype='uint8', crs='EPSG:3857', transform=Affine.from_gdal(*gt),
                    tiled=True, blockxsize=256, blockysize=256, compress='deflate') as ds:
                ds.write(source, 1)
                if overview:
                    ds.build_overviews([2, 4, 8, 16], Resampling.nearest)
            path.chmod(0o444)
            item = {'name': name, 'path': path.relative_to(root).as_posix(), 'angle': angle, 'shear': shear,
                    'overviews': overview, 'gt': gt, 'size': size, 'sha256': digest(path)}
            entries.append(item)
            print('fixture', name, item['sha256'], flush=True)
    write_json(manifest_path, entries)


def verify(root):
    root = Path(FIXTURE_ROOT or root).resolve()
    entries = json.loads((root / 'fixtures.json').read_text())
    for item in entries:
        # Keep all local reads within the selected, relocatable fixture root.
        item['path'] = str(root / 'fixtures' / (item['name'] + '.tif'))
        if digest(item['path']) != item['sha256']:
            raise RuntimeError('Fixture changed: ' + item['name'])
    print(f'Verified {len(entries)} immutable fixtures', flush=True)
    return entries


def session(username, password_file):
    s = requests.Session()
    s.auth = (username, Path(password_file).read_text().strip())
    return s


def checked(s, method, path, **kwargs):
    r = s.request(method, BASE + path, timeout=120, **kwargs)
    if not r.ok:
        raise RuntimeError(f'{method} {path}: HTTP {r.status_code}: {r.text[:500]}')
    return r


def snapshot(root, s):
    directory = root / 'config'
    directory.mkdir(parents=True, exist_ok=True)
    for path, filename in [('/rest/about/version.json', 'version.json'), ('/rest/services/wms/settings.xml', 'wms-original.xml'),
                           ('/rest/settings.xml', 'global-original.xml'),
                           ('/gwc/rest/gridsets/EPSG:900913.xml', 'grid-original.xml')]:
        destination = directory / filename
        if not destination.exists():
            destination.write_bytes(checked(s, 'GET', path).content)
    print((directory / 'version.json').read_text(), flush=True)


SLD = '''<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld">
 <NamedLayer><Name>affine_gray</Name><UserStyle><Title>Unstretched grayscale</Title>
 <FeatureTypeStyle><Rule><RasterSymbolizer><Opacity>1</Opacity><ChannelSelection>
 <GrayChannel><SourceChannelName>1</SourceChannelName></GrayChannel>
 </ChannelSelection></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer>
</StyledLayerDescriptor>'''


def publish(root, s):
    entries = verify(root)
    grid = ET.fromstring((root / 'config/grid-original.xml').read_bytes())
    grid.find('name').text = GRID
    grid.find('srs/number').text = '3857'
    for element, value in zip(grid.findall('extent/coords/double'), [-HALF, -HALF, HALF, HALF]):
        element.text = str(value)
    for z, element in enumerate(grid.findall('resolutions/double')):
        element.text = str(2 * HALF / (256 * (1 << z)))
    for z, element in enumerate(grid.findall('scaleNames/string')):
        element.text = f'{GRID}:{z}'
    grid.find('description').text = 'Isolated affine probe EPSG:3857 grid'
    checked(s, 'PUT', f'/gwc/rest/gridsets/{GRID}.xml', data=ET.tostring(grid), headers={'Content-Type': 'application/xml'})
    (root / 'config' / 'study-grid.xml').write_bytes(checked(s, 'GET', f'/gwc/rest/gridsets/{GRID}.xml').content)
    r = s.get(BASE + f'/rest/workspaces/{WS}.json', timeout=30)
    if r.status_code == 404:
        checked(s, 'POST', '/rest/workspaces', json={'workspace': {'name': WS}})
    else:
        r.raise_for_status()
    style = f'/rest/workspaces/{WS}/styles/affine_gray.sld'
    r = s.get(BASE + style, timeout=30)
    if r.status_code == 404:
        checked(s, 'POST', f'/rest/workspaces/{WS}/styles', params={'name': 'affine_gray'},
                data=SLD, headers={'Content-Type': 'application/vnd.ogc.sld+xml'})
    else:
        r.raise_for_status()
    for item in entries:
        name = item['name']
        store = f'/rest/workspaces/{WS}/coveragestores/{name}'
        if s.get(BASE + store + '.json', timeout=30).status_code == 404:
            checked(s, 'PUT', store + '/external.geotiff', params={'configure': 'first', 'coverageName': name},
                    data=str(Path(SERVER_FIXTURE_DIR) / Path(item['path']).name) if SERVER_FIXTURE_DIR else item['path'],
                    headers={'Content-Type': 'text/plain'})
        checked(s, 'PUT', f'/rest/layers/{WS}:{name}.json', json={'layer': {'defaultStyle': {'name': 'affine_gray', 'workspace': WS}}})
        cache_config(s, name, 0, 1)
        (root / 'config' / (name + '-coverage.json')).write_bytes(checked(s, 'GET', store + f'/coverages/{name}.json').content)
        print('published', name, flush=True)


def cache_config(s, name, gutter, metatile):
    path = f'/gwc/rest/layers/{WS}:{name}.xml'
    layer = ET.fromstring(checked(s, 'GET', path).content)
    for tag in ('metaWidthHeight', 'gutter', 'mimeFormats', 'gridSubsets'):
        old = layer.find(tag)
        if old is not None:
            layer.remove(old)
    size = ET.SubElement(layer, 'metaWidthHeight')
    for _ in range(2):
        ET.SubElement(size, 'int').text = str(metatile)
    ET.SubElement(layer, 'gutter').text = str(gutter)
    ET.SubElement(ET.SubElement(layer, 'mimeFormats'), 'string').text = 'image/png'
    grid = ET.SubElement(ET.SubElement(layer, 'gridSubsets'), 'gridSubset')
    ET.SubElement(grid, 'gridSetName').text = GRID
    ET.SubElement(grid, 'zoomStart').text = '0'
    ET.SubElement(grid, 'zoomStop').text = '24'
    checked(s, 'PUT', path, data=ET.tostring(layer), headers={'Content-Type': 'application/xml'})


def truncate(s, name, start=14, stop=24):
    checked(s, 'POST', f'/gwc/rest/seed/{WS}:{name}.json', json={'seedRequest': {
        'name': f'{WS}:{name}', 'srs': {'number': 3857}, 'zoomStart': start, 'zoomStop': stop,
        'format': 'image/png', 'type': 'truncate', 'threadCount': 1}})
    for _ in range(240):
        tasks = checked(s, 'GET', f'/gwc/rest/seed/{WS}:{name}.json').json().get('long-array-array', [])
        if not tasks:
            return
        time.sleep(.25)
    raise RuntimeError('Test-layer cache truncation timed out')


def tile(z, x, y):
    span = 2 * HALF / (1 << z)
    return [-HALF + x * span, HALF - (y + 1) * span, -HALF + (x + 1) * span, HALF - y * span]


def tile_at(z, x, y):
    span = 2 * HALF / (1 << z)
    return z, math.floor((x + HALF) / span), math.floor((HALF - y) / span)


def cases(item, quick=False):
    size = item['size']
    points = [(.5, .5), (.5, .125), (.31, .68), (.72, .87), (.001, .5), (.999, .5), (.5, .001), (.5, .999)]
    seen = set()
    for z in (18, 20, 22, 24) if quick else range(14, 25):
        for px, py in points[:4] if quick else points:
            t = tile_at(z, *world(item['gt'], px * size, py * size))
            if t not in seen:
                seen.add(t)
                yield t


@functools.lru_cache(maxsize=3)
def source_array(path):
    with Image.open(path) as image:
        return np.array(image)


def wms(name, bbox, interpolation='nearest neighbor', width=256, height=256, **extra):
    return {'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap', 'layers': f'{WS}:{name}',
            'styles': '', 'srs': 'EPSG:3857', 'bbox': ','.join(map(str, bbox)), 'width': width,
            'height': height, 'format': 'image/png', 'transparent': 'false', 'bgcolor': '0xFFFFFF',
            'interpolations': interpolation, 'format_options': 'antialias:off', **extra}


def request_image(s, item, t, route='wms', interpolation='nearest neighbor', extra=None, pad=0, analyze=True):
    bbox = tile(*t)
    if route == 'gwc':
        params = {'SERVICE': 'WMTS', 'VERSION': '1.0.0', 'REQUEST': 'GetTile', 'LAYER': f'{WS}:{item["name"]}',
                  'STYLE': '', 'FORMAT': 'image/png', 'TILEMATRIXSET': GRID,
                  'TILEMATRIX': f'{GRID}:{t[0]}', 'TILECOL': t[1], 'TILEROW': t[2]}
        path = '/gwc/service/wmts'
    else:
        res = (bbox[2] - bbox[0]) / 256
        expanded = [bbox[0] - pad * res, bbox[1] - pad * res, bbox[2] + pad * res, bbox[3] + pad * res]
        params = wms(item['name'], expanded, interpolation, 256 + 2 * pad, 256 + 2 * pad, **(extra or {}))
        path = '/wms'
    start = time.perf_counter()
    r = s.get(BASE + path, params=params, timeout=120)
    elapsed = time.perf_counter() - start
    if not r.ok or not r.headers.get('Content-Type', '').lower().startswith('image/png'):
        raise RenderFailure(r)
    metadata = {'name': item['name'], 'tile': list(t), 'route': route, 'interpolation': interpolation,
                'seconds': elapsed, 'bytes': len(r.content), 'url': r.url, 'status': r.status_code,
                'cache': r.headers.get('geowebcache-cache-result'), 'pad': pad}
    if not analyze:
        size = 256 + 2 * pad if route != 'gwc' else 256
        if r.content[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', r.content[16:24]) != (size, size):
            raise RuntimeError('Invalid PNG dimensions in performance response')
        return metadata, None, None, None, r.content
    im = Image.open(io.BytesIO(r.content))
    im.load()
    expected_size = 256 + 2 * pad if route != 'gwc' else 256
    if im.size != (expected_size, expected_size):
        raise RuntimeError(f'Wrong image size {im.size}')
    if pad:
        im = im.crop((pad, pad, pad + 256, pad + 256))
    ref, valid = expected(source_array(item['path']), item['gt'], bbox)
    result, holes = metrics(im, ref, valid)
    result.update(metadata)
    return result, im, holes, ref, r.content


def record(root, label, result, im, holes, ref, raw):
    directory = root / 'images' / label
    directory.mkdir(parents=True, exist_ok=True)
    stem = result['name'] + '_' + result['route'] + '_' + '_'.join(map(str, result['tile']))
    destination = directory / stem
    destination.with_suffix('.png').write_bytes(raw)
    if result['missing_pixels']:
        Image.fromarray(holes.astype(np.uint8) * 255).save(str(destination) + '-holes.png')
        Image.fromarray(ref).save(str(destination) + '-expected.png')
    if result.get('pad'):
        im.save(str(destination) + '-crop.png')
    result['image'] = str(destination.relative_to(root)) + '.png'
    with (root / (label + '.jsonl')).open('a') as f:
        f.write(json.dumps(result, allow_nan=False) + '\n')


def scan(root, s, quick=False, names=None, label='baseline', mosaic=False, extra=None, routes=None, pad=0):
    entries = verify(root)
    if names:
        entries = [i for i in entries if i['name'] in names.split(',')]
    destination = root / (label + '.jsonl')
    completed = set()
    for path in (destination, root / (label + '-bilinear.jsonl'), root / (label + '-errors.jsonl')):
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                completed.add((row['name'], row['route'], row['interpolation'], tuple(row['tile'])))
    for item in entries:
        if mosaic:
            item = dict(item, name='mosaic_' + item['name'])
        counts = {}
        for route, interpolation in routes or [('wms', 'nearest neighbor'), ('wms', 'bilinear'), ('gwc', 'nearest neighbor')]:
            sublabel = label + ('-bilinear' if interpolation == 'bilinear' else '')
            for t in cases(item, quick):
                if (item['name'], route, interpolation, t) in completed:
                    continue
                try:
                    r = request_image(s, item, t, route, interpolation, extra=extra, pad=pad if route == 'wms' else 0)
                    record(root, sublabel, *r)
                    counts[route + '/' + interpolation] = counts.get(route + '/' + interpolation, 0) + r[0]['missing_pixels']
                except RenderFailure as error:
                    failure = {'name': item['name'], 'route': route, 'interpolation': interpolation,
                               'tile': list(t), 'url': error.url, 'status': error.status, 'error': str(error)}
                    with (root / (label + '-errors.jsonl')).open('a') as f:
                        f.write(json.dumps(failure) + '\n')
                    path = root / 'errors' / (label + '-' + item['name'] + '-' + route + '-' + interpolation + '-' + '-'.join(map(str, t)) + '.xml')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(error.body)
                    print('render failure', failure, flush=True)
        print(item['name'], counts, flush=True)
    verify(root)


def configure(root, s, gutter, metatile):
    for item in verify(root):
        cache_config(s, item['name'], gutter, metatile)
        truncate(s, item['name'])
        name = item['name']
        (root / 'config' / f'{name}-gwc-g{gutter}-m{metatile}.xml').write_bytes(
            checked(s, 'GET', f'/gwc/rest/layers/{WS}:{name}.xml').content)
    write_json(root / f'config/gutter-{gutter}-metatile-{metatile}.json',
               {'gutter': gutter, 'metatile': metatile, 'grid': GRID})


def regression(root, s, pad=0):
    """Live regression for the original interior triangles and affine edge crash."""
    entries = {i['name']: i for i in verify(root)}
    selected = [('rot30_base', (24, 10021003, 6797199)),
                ('rot30_base', (24, 10021196, 6798186)),
                ('rot45_base', (20, 626332, 424887)),
                ('shear_base', (22, 2505547, 1699529)),
                ('rotm30_base', (20, 626306, 424906))]
    failures = []
    for name, t in selected:
        for route in ('wms', 'gwc'):
            try:
                response = request_image(s, entries[name], t, route=route, pad=pad if route == 'wms' else 0)
                record(root, 'regression', *response)
                row = response[0]
                if row['valid_pixels'] == 65536 and row['missing_pixels']:
                    failures.append(f'{name} {t} {route}: interior pixels missing')
                if row['valid_pixels'] == 65536 and (row['mae_valid_nonblank'] is None or row['mae_valid_nonblank'] > .1):
                    failures.append(f'{name} {t} {route}: wrong source coordinates or blur')
            except RenderFailure as error:
                failures.append(f'{name} {t} {route}: {error}')
    write_json(root / 'regression-result.json', {'passed': not failures, 'failures': failures})
    if failures:
        raise AssertionError('\n'.join(failures))
    print('PASS: interior triangles, tile rows, georeferencing and footprint exception regression', flush=True)


def main():
    parser = argparse.ArgumentParser(description='Generate or verify immutable synthetic affine fixtures')
    parser.add_argument('stage', choices=['prepare', 'verify'])
    parser.add_argument('--root', type=Path, default=Path('.runs/fixtures'))
    parser.add_argument('--size', type=int, default=4096, help='Rendering validation requires 4096')
    args = parser.parse_args()
    if args.stage == 'prepare':
        fixtures(args.root, args.size)
    else:
        verify(args.root)


if __name__ == '__main__':
    main()
