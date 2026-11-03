"""Export evidence for the combined research candidate, with explicit validity totals."""
import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
from . import probe


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quality', type=Path, required=True)
    p.add_argument('--rendering', type=Path, required=True)
    p.add_argument('--performance', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('docs/research'))
    a = p.parse_args()
    q = json.loads((a.quality/'result.json').read_text())
    r = json.loads((a.rendering/'result.json').read_text())
    b = json.loads((a.performance/'result.json').read_text())
    if not q['complete'] or not b['complete']:
        raise ValueError('Incomplete experiment')
    a.output.mkdir(parents=True, exist_ok=True)
    for name, data in [('combined-quality', q), ('combined-rendering', r), ('combined-performance', b)]:
        probe.write_json(a.output/(name+'.json'), data)
    shutil.copyfile(a.performance/'requests.jsonl.gz', a.output/'combined-requests.jsonl.gz')
    keys = ('missing', 'spurious', 'alpha_mismatch', 'color_mismatch')
    totals = {key: sum(x.get(key, 0) for x in q['quality']) for key in keys}
    errors = sum(bool(x.get('error')) for x in q['quality'])
    repeated = [x for x in b['quality'] if x['variant'] == 'both']
    repeated_bad = sum(bool(x.get('error') or x.get('alpha_mismatch') or x.get('color_mismatch')) for x in repeated)
    probe.write_json(a.output/'combined-verdict.json', dict(quality_checks=len(q['quality']),
        response_errors=errors, **totals, repeated_checks=len(repeated), repeated_failed_checks=repeated_bad,
        typed_passed=not (errors or any(totals.values()) or repeated_bad),
        original_rendering_passed=r['passed']))
    lines = ['# Combined affine candidate', '',
        'Branch: `codex/affine-complete-candidate`. Published baseline: `fcbf811`. '
        'This integrates the mask and precision experiments, with additional fixes found during integration. '
        '**Historical integration stage; incorporated into the optimized fix on this repository’s main. Not accepted upstream.**', '',
        '## Changes', '',
        '1. Preserve a source-grid footprint mask while bypassing the premature map-space crop.',
        '2. Add a NoData-validity mask before affine background substitution, preserving valid zero elevations.',
        '3. Explicitly write zero outside transformed binary masks; never extend their border as valid data.',
        '4. Keep affine bounds and nearest/binary sample coordinates in double precision. Use 28-bit scanline fractions and widen products before multiplication.',
        '5. Compute nearest-neighbor output bounds from pixel centers. Separately rounding the origin and truncating width can omit an otherwise valid final column or row.', '',
        '## Validity', '',
        f'The independent typed matrix performs **{len(q["quality"]):,} checks**, with {errors} response errors, '
        f'{totals["missing"]} missing pixels, {totals["spurious"]} spurious opaque pixels, '
        f'{totals["alpha_mismatch"]} alpha mismatches and {totals["color_mismatch"]} color mismatches. '
        'It covers RGB, RGBA, four-band UInt16 and Float32 with numeric/NaN NoData; north-up/30° rotation; '
        'base images/overviews; gutters 0/1. Existing tolerances remain 2/255 for color and 1/255 for alpha, with no footprint erosion. '
        f'A fresh paired performance run repeats {len(repeated):,} candidate image checks, with {repeated_bad} failed checks.', '',
        'The original grayscale reproduction covers 14 fixtures including negative rotation, 45°/75° rotation and shear, '
        'on WMS and GWC. This older oracle counts missing data, not full color/alpha equality. Results:', '',
        '| Treatment | Route | Response errors | Missing pixels | Missing interior pixels |',
        '|---|---|---:|---:|---:|']
    for treatment in ('patched-g0', 'patched-g1'):
        for route, result in r['treatments'][treatment].items():
            lines.append(f'| {treatment} | {route} | {result["errors"]} | {result["missing_pixels"]:,} | {result["interior_missing_pixels"]:,} |')
    lines += ['', 'Direct Java regressions cover 32,448 clipping cases, scanline drift, integer-product overflow, '
        'a rendered edge sample, an entire transformed binary mask, and a mask sample at a fractional affine boundary. '
        'The original library fails the clipping regression; the candidate passes the full Java test. '
        'Python source/patch/build checks and JavaScript adapter checks also pass.', '',
        '## Exploratory performance', '',
        f'{sum(x["summary"]["requests"] for x in b["blocks"]):,} timed requests with '
        f'{sum(x["summary"]["errors"] for x in b["blocks"]):,} response/cache errors. '
        '**One fresh JVM pair**, three rounds, 1/6 clients, WMS/GWC MISS/GWC HIT. '
        'This is a paired sanity check, not the earlier three-JVM benchmark. Other test loads finish before timing begins. '
        'WMS timing remains opaque; image validity is checked separately with transparent output. '
        'Per-case numbers below are medians of single-client WMS fixture medians across rounds and overview variants.', '',
        '| Case | Rotation | Stock ms | Candidate ms |', '|---|---:|---:|---:|']
    ratios = []
    for kind in ('rgb', 'rgba', 'multispectral', 'dem', 'dem_nan'):
        for angle in (0, 30):
            values = defaultdict(list)
            for block in b['blocks']:
                if block['profile'] == 'wms' and block['concurrency'] == 1:
                    for name, stats in block['summary']['by_fixture'].items():
                        if name.startswith(f'{kind}_r{angle}_') and stats['median_ms'] is not None:
                            values[block['variant']].append(stats['median_ms'])
            lines.append(f'| {kind} | {angle}° | {np.median(values["stock"]):.2f} | {np.median(values["both"]):.2f} |')
            if angle == 30: ratios.append(float(np.median(values['both']) / np.median(values['stock'])))
    lines += ['', f'**Performance cost:** rotated single-client WMS medians are {min(ratios):.2f}–{max(ratios):.2f}× stock in this run. This candidate restores correctness at a measurable cost; optimizing mask processing is a separate next step.', '', 'The candidate avoids premature map-space crop/mosaic work, while restoring validity handling. '
        'These measurements do not isolate individual operation costs. Repeated JVMs and realistic datasets are still needed '
        'before making a general performance claim.', '',
        '## Evidence and scope', '',
        '[Typed measurements](combined-quality.json) · [Original rendering reproduction](combined-rendering.json) · '
        '[Performance measurements](combined-performance.json) · [Request timings](combined-requests.jsonl.gz) · '
        '[Machine-readable verdict](combined-verdict.json)', '',
        'Source TIFF hashes are unchanged; libraries are built against the pinned official GeoServer 3.0.2 image. '
        'The previous main-branch report remains historical evidence. Rejected prototypes are discussed in the '
        '[mask experiment](mask.md) and [precision experiment](precision.md).', '',
        'Remaining scope: no claim for arbitrary reprojection, bilinear/bicubic rendering, all GeoTIFF layouts or '
        'multi-band NoData combinations. A finite fixed-point scanline increment still has a precision limit. '
        'The broader ImageN precision changes need upstream interpolation regressions and review. '
        'The GeoTools bypass must also be checked against projection-domain clipping and real ImageMosaic datasets. '
        'Native RGBA is tested; explicitly selecting RGB channels is a different style and can drop alpha independently of this patch.', '',
        '## Reproduce', '', '```bash', 'uv sync --frozen --all-extras',
        'uv run python -m affine_fix.typed_suite --root .runs/typed-candidate --quality-only --variants both',
        'uv run affine-reproduce --root .runs/rendering-candidate',
        'uv run python -m affine_fix.typed_suite --root .runs/performance-candidate --replicates 1',
        'uv run python -m affine_fix.research_report --quality .runs/typed-candidate --rendering .runs/rendering-candidate --performance .runs/performance-candidate',
        '```', '']
    (a.output/'combined.md').write_text('\n'.join(lines))
    print(a.output/'combined.md')


if __name__ == '__main__':
    main()
