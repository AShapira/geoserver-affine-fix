"""Deterministic benchmark fixtures, interior requests and an independent pixel oracle."""
import json
from pathlib import Path

import numpy as np

from . import lab, probe


def pixels(size, x, y):
    """Evaluate the synthetic pattern at indices; never allocate a full large TIFF."""
    x, y = np.broadcast_arrays(np.asarray(x, dtype=np.uint32), np.asarray(y, dtype=np.uint32))
    out = np.where((x // 4 + y // 4) % 2, 208, 48)
    out = np.where((y >= size // 4) & (y < size // 2), 32 + x * 191 // max(1, size - 1), out)
    out = np.where((y >= size // 2) & (y < 3 * size // 4), 32 + ((x * 73856093 ^ y * 19349663) % 192), out)
    out = np.where(y >= 3 * size // 4,
                   np.where((x % 16 < 2) | (y % 32 < 2) | (x > y), 208, 48), out)
    return out.astype(np.uint8)


def fixtures(root):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    from rasterio.windows import Window

    root = Path(root)
    manifest = root / 'fixtures.json'
    if not manifest.exists():
        probe.fixtures(root)
    entries = json.loads(manifest.read_text())
    if len(entries) == 17:
        lab.validate_fixture_set(probe.verify(root), 'benchmark')
        return
    lab.validate_fixture_set(probe.verify(root))
    size = 16384
    for name, angle, overview in [('large_rot0_base', 0, False), ('large_rot30_base', 30, False),
                                   ('large_rot30_ovr', 30, True)]:
        path = root / 'fixtures' / (name + '.tif')
        if path.exists():
            raise RuntimeError('Refusing to overwrite an unmanifested fixture: ' + str(path))
        gt = probe.affine(angle, size=size)
        with rasterio.open(path, 'w', driver='GTiff', width=size, height=size, count=1,
                           dtype='uint8', crs='EPSG:3857', transform=Affine.from_gdal(*gt),
                           tiled=True, blockxsize=256, blockysize=256, compress='deflate') as ds:
            for y in range(0, size, 1024):
                for x in range(0, size, 1024):
                    ds.write(pixels(size, np.arange(x, x + 1024)[None, :],
                                    np.arange(y, y + 1024)[:, None]), 1, window=Window(x, y, 1024, 1024))
            if overview:
                ds.build_overviews([2, 4, 8, 16], Resampling.nearest)
        path.chmod(0o444)
        entries.append({'name': name, 'path': path.relative_to(root).as_posix(), 'angle': angle,
                        'shear': False, 'overviews': overview, 'gt': gt, 'size': size,
                        'sha256': probe.digest(path)})
        print('Large fixture:', name, flush=True)
    probe.write_json(manifest, entries)
    lab.validate_fixture_set(entries, 'benchmark')


def interior(item, tile, gutter=1):
    bbox = probe.tile(*tile)
    res = (bbox[2] - bbox[0]) / 256
    # Include the full padded extent, not just pixel centres.
    xs = np.array([bbox[0] - gutter * res, bbox[2] + gutter * res])
    ys = np.array([bbox[1] - gutter * res, bbox[3] + gutter * res])
    col, row = probe.pixel_coordinates(item['gt'], xs[None, :], ys[:, None])
    return bool(np.all((col >= 0) & (row >= 0) & (col < item['size']) & (row < item['size'])))


def tile_jobs(item, zooms=(16, 18, 20, 22, 24), counts=(4, 15, 15, 15, 15), point=(.5, .6)):
    jobs = []
    offsets = sorted(((x, y) for x in range(-8, 9) for y in range(-8, 9)),
                     key=lambda p: (p[0] ** 2 + p[1] ** 2, p))
    for zoom, count in zip(zooms, counts, strict=True):
        _, cx, cy = probe.tile_at(zoom, *probe.world(item['gt'], *(p * item['size'] for p in point)))
        found = 0
        for dx, dy in offsets:
            tile = [zoom, cx + dx, cy + dy]
            if interior(item, tile):
                jobs.append({'name': item['name'], 'tile': tile})
                found += 1
                if found == count:
                    break
        if found != count:
            raise ValueError('Insufficient interior tiles for ' + item['name'])
    return jobs


def workloads(entries):
    by_name = {e['name']: e for e in entries}
    core = [job for name in ('rot0_base', 'rot30_base', 'rot30_ovr', 'shear_base')
            for job in tile_jobs(by_name[name])]
    large = [job for name in ('large_rot0_base', 'large_rot30_base', 'large_rot30_ovr')
             for job in tile_jobs(by_name[name], zooms=(14, 16, 18, 20, 22))]
    geometry = [job for item in entries if not item['name'].startswith('large_')
                for point in ((.5, .15), (.5, .35), (.5, .6), (.5, .85))
                for job in tile_jobs(item, zooms=(20,), counts=(4,), point=point)]
    result = {'core': core, 'large': large, 'geometry': geometry, 'control': core[::4]}
    for jobs in result.values():
        keys = {(j['name'], *j['tile']) for j in jobs}
        if len(keys) != len(jobs):
            raise ValueError('Duplicate tiles would invalidate a cache-MISS block')
    return result


def reference(item, tile, size=256):
    bbox = probe.tile(*tile)
    x = bbox[0] + (np.arange(size) + .5) * (bbox[2] - bbox[0]) / size
    y = bbox[3] - (np.arange(size) + .5) * (bbox[3] - bbox[1]) / size
    col, row = probe.pixel_coordinates(item['gt'], x[None, :], y[:, None])
    ci, ri = np.floor(col).astype(int), np.floor(row).astype(int)
    valid = (ci >= 0) & (ri >= 0) & (ci < item['size']) & (ri < item['size'])
    return pixels(item['size'], np.maximum(ci, 0), np.maximum(ri, 0)), valid
