"""Export typed-raster evidence, including failures and excluded fixture trials."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import shutil
import numpy as np
from . import probe
from .typed_suite import KINDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--rgba-run', type=Path)
    parser.add_argument('--rgba-diagnostic', type=Path)
    parser.add_argument('--output', type=Path, default=Path('docs/typed-raster-tests'))
    args = parser.parse_args()
    initial = json.loads((args.run/'result.json').read_text())
    rgba = json.loads((args.rgba_run/'result.json').read_text()) if args.rgba_run else initial
    if not initial['complete'] or not rgba['complete']:
        raise RuntimeError('Incomplete run')
    sources = {kind: rgba if kind == 'rgba' else initial for kind in KINDS}
    args.output.mkdir(parents=True, exist_ok=True)
    probe.write_json(args.output/'results.json', initial)
    shutil.copyfile(args.run/'requests.jsonl.gz', args.output/'requests.jsonl.gz')
    if args.rgba_run:
        probe.write_json(args.output/'rgba-results.json', rgba)
        shutil.copyfile(args.rgba_run/'requests.jsonl.gz', args.output/'rgba-requests.jsonl.gz')
    quality = [q for kind, source in sources.items() for q in source['quality']
               if q['name'].startswith(kind+'_r')]
    timing = [s for kind, source in sources.items() for b in source['blocks']
              for name, s in b['summary']['by_fixture'].items() if name.startswith(kind+'_r')]
    validation = []
    for kind in KINDS:
        for angle in (0, 30):
            for variant in ('stock', 'both'):
                for gutter in (0, 1):
                    rows = [x for x in quality if x['variant'] == variant and x['gutter'] == gutter
                            and x['name'].startswith(f'{kind}_r{angle}_')]
                    summary = dict(kind=kind, angle=angle, variant=variant, gutter=gutter,
                                   checks=len(rows), response_errors=sum(bool(x.get('error')) for x in rows))
                    summary.update({key: sum(x.get(key, 0) for x in rows)
                                    for key in ('missing', 'spurious', 'alpha_mismatch', 'color_mismatch')})
                    summary['passed'] = bool(rows) and not any(summary[key] for key in
                        ('response_errors', 'alpha_mismatch', 'color_mismatch'))
                    validation.append(summary)
    probe.write_json(args.output/'validation.json', dict(
        passed=all(x['passed'] for x in validation), checks=len(quality), cases=validation))
    # Per-fixture latency evidence for every route, client count, JVM and round.
    # Whole-block elapsed time is deliberately omitted: it is not fixture throughput.
    with (args.output/'performance.csv').open('w', newline='') as output:
        fields = ['kind', 'fixture', 'replicate', 'round', 'variant', 'profile', 'concurrency',
                  'requests', 'errors', 'median_ms', 'p95_ms']
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for kind, source in sources.items():
            for block in source['blocks']:
                for name, stats in block['summary']['by_fixture'].items():
                    if name.startswith(kind+'_r'):
                        row = {key: block[key] for key in fields[2:7]}
                        row.update({key: stats[key] for key in fields[7:]})
                        writer.writerow(dict(row, kind=kind, fixture=name))
    lines = ['# RGB, alpha, multispectral and elevation tests', '',
        '**The candidate fix fails broader transparency/NoData validity checks. It is not ready for general deployment.**', '',
        'Official GeoServer 3.0.2, pinned libraries and freshly built patches. Five data cases × north-up/30° rotation '
        '× no overviews/nearest overviews: 20 synthetic 2048² tiled DEFLATE TIFFs. The cases are 8-bit RGB, RGBA, '
        'four-band UInt16, Float32 with −9999 NoData, and Float32 with NaN NoData.', '',
        'RGBA contains transparent borders, an internal hole and alpha 128, stored as non-premultiplied alpha. '
        'The generator verifies the alpha tag after reopening each TIFF. UInt16 rendering selects bands 4/2/1 '
        'with explicit 0–65535 contrast scaling; band 3 contains unrelated values. Elevation includes valid negative '
        'and zero values and an explicit four-color value map. North-up controls use the same data and styles as their rotated counterparts.', '']
    if args.rgba_run:
        lines += ['## Evidence correction', '',
            'The initial run incorrectly stored the RGBA fourth band as undefined. Its RGBA results are excluded from '
            '**every table and count below**. Those files caused transparent-PNG encoder failures in both variants; '
            'that trial is not evidence of a GeoServer RGBA defect. The corrected, alpha-tagged fixtures were rerun '
            'through all validity and performance cases with three fresh JVM pairs.', '',
            'RGB, UInt16 and elevation results come from the initial mixed workload, which also contained the excluded '
            'RGBA requests. Correct RGBA results come from a separate RGBA-only workload. Each stock/patched pair '
            'uses identical inputs and order, but the workload mix differs between runs. Do not combine their overall '
            'throughput, CPU or memory totals. Raw initial results retain the invalid trial for audit; use rgba-results.json '
            'for RGBA. The current generator produces the corrected fixtures in a single run.', '']
    lines += ['## Validity', '',
        f'{len(quality):,} WMS image checks cover both servers and gutters 0/1. Nearest WMS requests use transparent PNG. '
        'The oracle independently inverse-maps output pixel centers to source indices and evaluates the synthetic data '
        'and declared style, including footprint, alpha and NoData. There is no erosion of the valid footprint. '
        'Color tolerance is 2/255 per channel; alpha tolerance is 1/255. RGB under fully transparent expected pixels is ignored. '
        'Zooms 20/22/24 cover interior colors, holes, partial alpha and outer boundaries. The table uses gutter 1 and '
        'combines both overview variants. Counts are evaluated output pixels, including overlapping requests, '
        'not unique source pixels. Gutter-0 measurements and explicit pass/fail flags are in [validation.json](validation.json).', '',
        '| Case | Rotation | Variant | Checks | Response errors | Missing valid | Spurious opaque | Alpha mismatches | Color mismatches |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for kind in KINDS:
        for angle in (0, 30):
            for variant in ('stock', 'both'):
                q = [x for x in quality if x['variant'] == variant and x['gutter'] == 1
                     and x['name'].startswith(f'{kind}_r{angle}_')]
                counts = [len(q), sum(bool(x.get('error')) for x in q)]
                counts += [sum(x.get(key, 0) for x in q) for key in ('missing', 'spurious', 'alpha_mismatch', 'color_mismatch')]
                lines.append(f'| {kind} | {angle}° | {variant} | '+' | '.join(f'{n:,}' for n in counts)+' |')
    rgba_counts = {x['variant']: x for x in validation
                   if x['kind'] == 'rgba' and x['angle'] == 30 and x['gutter'] == 1}
    lines += ['',
        'All five north-up controls pass these gutter-1 checks. The combined fix eliminates the measured missing valid '
        'pixels in rotated RGB, UInt16 and elevation, but **increases spurious opacity**. RGB/UInt16 errors are outside '
        'the footprint; elevation additionally loses transparency inside NoData holes. Keeping source pixels available '
        'must also preserve the masks that hide invalid areas. These results do not isolate which patch causes the regressions.', '',
        'Correctly tagged RGBA with native channel interpretation improves substantially: missing rotated pixels fall '
        f'from {rgba_counts["stock"]["missing"]:,} to {rgba_counts["both"]["missing"]:,}, '
        f'with {rgba_counts["both"]["spurious"]:,} spurious opaque pixels, '
        f'{rgba_counts["both"]["alpha_mismatch"]:,} alpha mismatches and '
        f'{rgba_counts["both"]["color_mismatch"]:,} color mismatches remaining. '
        'This is a large improvement, not an exact validity pass. Small boundary discrepancies are retained in the results.', '',
        '![Actual footprint and NoData failures](transparency.png)', '',
        '## Performance', '',
        f'{sum(s["requests"] for s in timing):,} included timed requests; '
        f'{sum(s["errors"] for s in timing):,} HTTP/image/cache-state errors. '
        'Three fresh JVM pairs, three rounds per pair, 1/6 clients; direct WMS, GWC MISS and GWC HIT. '
        'Two WMS warmup passes per server. Caches are cleared for MISS and primed for HIT; every timed cache header '
        'is checked. Requests use paired shuffled order. Validity decoding is outside timing. Direct WMS timing uses '
        'opaque output (the existing benchmark contract); transparent validity is tested separately. Each server has '
        'two CPU cores of quota and a 2 GiB maximum heap. Only one server receives benchmark load at a time.', '',
        '**These timings include incorrect images. A speedup in a failing case does not establish a valid optimization.**', '',
        'Single-client direct-WMS medians combine base/overview fixture medians across rounds within each JVM, '
        'then take the median across three JVMs. The per-JVM range is not a confidence interval. '
        'All routes and client counts are available in [the per-fixture latency table](performance.csv), including p95, errors, JVM and round.', '',
        '| Case | Rotation | Stock ms | Both fixes ms | Stock JVM range | Fixed JVM range |',
        '|---|---:|---:|---:|---:|---:|']
    for kind in KINDS:
        for angle in (0, 30):
            stats = {}
            for variant in ('stock', 'both'):
                values = defaultdict(list)
                for block in sources[kind]['blocks']:
                    if block['variant'] == variant and block['profile'] == 'wms' and block['concurrency'] == 1:
                        for name, s in block['summary']['by_fixture'].items():
                            if name.startswith(f'{kind}_r{angle}_') and s['median_ms'] is not None:
                                values[block['replicate']].append(s['median_ms'])
                v = [float(np.median(x)) for x in values.values()]
                stats[variant] = (np.median(v), min(v), max(v))
            a, b = stats['stock'], stats['both']
            lines.append(f'| {kind} | {angle}° | {a[0]:.2f} | {b[0]:.2f} | {a[1]:.2f}–{a[2]:.2f} | {b[1]:.2f}–{b[2]:.2f} |')
    lines += ['',
        'The intended speed benefit is less intermediate crop/mask processing before affine rendering. These measurements '
        'are consistent with that explanation, but do not isolate the time saved by each operation. In the new failing '
        'cases, skipped transparency work is also a correctness loss. Differences in north-up controls should be treated '
        'as run variability unless a further controlled experiment establishes a repeatable effect.', '']
    if args.rgba_diagnostic:
        diagnostic = json.loads((args.rgba_diagnostic/'result.json').read_text())
        probe.write_json(args.output/'rgba-diagnostic.json', diagnostic)
        lines += ['## RGBA style and encoder checks', '',
            f'An additional {len(diagnostic):,} image checks compare PNG and PNG8, native RGBA interpretation and '
            'explicit RGB channel selection. All responses encode successfully with properly tagged fixtures. '
            'PNG and PNG8 give identical mismatch counts in this small synthetic palette. Native RGBA preserves '
            'the tested alpha values in the north-up control. Explicit RGB channel selection drops alpha even in '
            'the stock north-up control: it is not an equivalent style for testing preservation of the source alpha. '
            'The main RGBA table therefore uses native interpretation. This style-dependent behavior is separate '
            'from the patch regression. [All diagnostic rows](rgba-diagnostic.json).', '']
    lines += ['## Reproduce', '', '```bash',
        'uv run python -m affine_fix.typed_suite --root .runs/typed-3.0.2',
        'uv run python -m affine_fix.typed_report --run .runs/typed-3.0.2',
        'uv run python -m affine_fix.typed_figures --run .runs/typed-3.0.2', '```', '',
        'For the two-run evidence published here, the report additionally uses '
        '`--rgba-run .runs/typed-rgba-3.0.2 --rgba-diagnostic .runs/rgba-encoder-check`. '
        'Run an RGBA-only matrix with `--kinds rgba`; run the style/encoder diagnostic with '
        '`uv run python -m affine_fix.rgba_diagnostic --run RUN --root NEW_DIRECTORY`.', '',
        '[Initial measurements and fixture hashes](results.json) · [Initial timed samples](requests.jsonl.gz)']
    if args.rgba_run:
        lines += ['[Corrected RGBA measurements](rgba-results.json) · [Corrected RGBA timed samples](rgba-requests.jsonl.gz)']
    lines += ['',
        'The runner builds against the pinned official image and removes only its labelled test containers. '
        'Source TIFF hashes are checked at completion. Credentials, source TIFFs and response PNGs stay in ignored '
        'run directories. The standard grayscale catalog bootstrap does not enter these typed measurements.', '',
        'Scope limits: synthetic fixtures, one CRS, nearest interpolation, two orientations, one machine. '
        'This does not certify other styles, reprojection, all compression/interleave layouts, or all numeric types. '
        'GWC timing checks PNG headers, dimensions and cache state; it does not decode every timed image or apply a separate per-pixel WMTS oracle. '
        'The two corrections were tested together; attribution to one correction requires an isolation run.', '']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(args.output)


if __name__ == '__main__':
    main()
