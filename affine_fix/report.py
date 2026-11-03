"""Create reproducible README figures and a compact report from a completed run."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from . import probe


def sample(run, label, name, tile):
    treatment = label.split('-')[0]
    rows = [json.loads(line) for line in (run / treatment / (label + '.jsonl')).read_text().splitlines()]
    row = next(r for r in rows if r['name'] == name and r['tile'] == list(tile) and r['route'] == 'wms')
    path = run / treatment / row['image']
    if row['pad']:
        path = path.with_name(path.stem + '-crop.png')
    with Image.open(path) as image:
        return row, np.array(image.convert('RGB'))


def comparison(run, destination, title, name, tile):
    probe.FIXTURE_ROOT = None
    fixture = next(e for e in probe.verify(run / 'fixtures') if e['name'] == name)
    reference, valid = probe.expected(probe.source_array(fixture['path']), fixture['gt'], probe.tile(*tile))
    if not valid.all():
        raise ValueError('README example must be entirely inside the raster footprint')
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.5), layout='constrained')
    fig.suptitle(title + '\nOfficial GeoServer 3.0.2 · identical source TIFF and map extent', fontsize=16, fontweight='bold')
    samples = {}
    for row_index, gutter in enumerate((0, 1)):
        for col, treatment in enumerate(('stock', 'patched')):
            label = f'{treatment}-g{gutter}'
            result, image = sample(run, label, name, tile)
            samples[label] = {key: result[key] for key in ('name', 'tile', 'route', 'pad', 'valid_pixels', 'missing_pixels', 'mae_valid_nonblank')}
            axes[row_index, col].imshow(image, interpolation='nearest')
            axes[row_index, col].set_title(f'{treatment.capitalize()} · gutter {gutter}\n{result["missing_pixels"]:,} missing pixels', fontsize=12)
        axes[row_index, 2].imshow(reference, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
        axes[row_index, 2].set_title('Independent expected pixels\nOriginal affine transform + nearest sampling', fontsize=11)
    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color('#cbd5e1')
    fig.savefig(destination, dpi=160, facecolor='white')
    plt.close(fig)
    return samples


def clipping_figure(destination):
    fig, ax = plt.subplots(figsize=(10, 3.6), layout='constrained')
    fig.suptitle('ImageN: respect the exclusive upper source bound', fontsize=16, fontweight='bold')
    ax.axvspan(-.1, 2, color='#e2e8f0', alpha=.5)
    for y, label, xs, color in [(2, 'Source interval [0, 2)', [0, 1], '#334155'),
                               (1, 'Stock clipping: [0, 3)', [0, 1, 2], '#c2410c'),
                               (0, 'Patched clipping: [0, 2)', [0, 1], '#047857')]:
        ax.scatter(xs, [y] * len(xs), s=140, c=color, zorder=3)
        ax.text(-.35, y, label, ha='right', va='center', fontsize=12, color=color)
    ax.scatter([2], [2], s=140, facecolors='white', edgecolors='#334155', linewidths=2, zorder=4)
    ax.annotate('2 is outside the source\nStock includes this invalid sample', xy=(2, 1), xytext=(2.5, 1.55),
                fontsize=11, color='#9a3412', arrowprops={'arrowstyle': '->', 'color': '#9a3412'})
    ax.set_xlim(-2.65, 4.2)
    ax.set_ylim(-.5, 2.6)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xlabel('Source coordinate (illustrative unit-step scanline)', fontsize=11)
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(destination, dpi=160, facecolor='white')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('docs'))
    args = parser.parse_args()
    report = json.loads((args.run / 'result.json').read_text())
    if not report['passed']:
        raise ValueError('Cannot publish an incomplete or failed reproduction as validation')
    assets = args.output / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans'})
    report['illustrations'] = {
        'triangles': comparison(args.run, assets / 'triangles.png', 'Missing triangles in a rotated raster',
                                'rot30_base', (24, 10021196, 6798186)),
        'checkerboard': comparison(args.run, assets / 'checkerboard.png', 'Preserving sharp source pixels',
                                   'rot30_base', (20, 626312, 424824)),
    }
    clipping_figure(assets / 'scanline-bounds.png')
    report['cache'] = [{k: row[k] for k in ('route', 'tile', 'cache', 'missing_pixels')} for row in report['cache']]
    probe.write_json(args.output / 'validation.json', report)
    print('Wrote three figures and validation.json to', args.output)


if __name__ == '__main__':
    main()
