"""Export a correctness-gated mask optimization comparison against a correct baseline."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import shutil
import numpy as np
from . import probe
from .typed_suite import KINDS

BASELINE = 'c9aff37f393feb0638add12a2ce63d67f0f00d84'


def quality_verdict(rows):
    keys = ('missing', 'spurious', 'alpha_mismatch', 'color_mismatch')
    return dict(checks=len(rows), errors=sum(bool(x.get('error')) for x in rows),
                **{key: sum(x.get(key, 0) for x in rows) for key in keys})


def case_timings(blocks, kind, angle):
    by_rep = defaultdict(list)
    for block in blocks:
        if block['profile'] == 'wms' and block['concurrency'] == 1:
            for name, stats in block['summary']['by_fixture'].items():
                if name.startswith(f'{kind}_r{angle}_'):
                    by_rep[block['replicate'], block['variant']].append(stats['median_ms'])
    reps = sorted({rep for rep, _ in by_rep})
    paired = [dict(replicate=rep, baseline_ms=float(np.median(by_rep[rep, 'stock'])),
                   optimized_ms=float(np.median(by_rep[rep, 'both']))) for rep in reps]
    for row in paired:
        row['reduction_percent'] = 100 * (1 - row['optimized_ms'] / row['baseline_ms'])
    return dict(kind=kind, angle=angle, replicates=paired,
                baseline_ms=float(np.median([x['baseline_ms'] for x in paired])),
                optimized_ms=float(np.median([x['optimized_ms'] for x in paired])),
                median_reduction_percent=float(np.median([x['reduction_percent'] for x in paired])))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('quality', 'performance', 'rendering', 'profile'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('docs/research'))
    a = p.parse_args()
    data = {name: json.loads((getattr(a, name)/'result.json').read_text())
            for name in ('quality', 'performance', 'rendering', 'profile')}
    q, b, r, f = (data[n] for n in ('quality', 'performance', 'rendering', 'profile'))
    if not all(x['complete'] for x in (q, b, f)) or not b.get('baseline_patch_build'):
        raise ValueError('Need complete runs and an explicitly patched correct baseline')
    # A faster renderer is useful only if both sides meet the same oracle.
    checks = {
        'optimized': quality_verdict(q['quality']),
        'paired_optimized': quality_verdict([x for x in b['quality'] if x['variant'] == 'both']),
        'paired_baseline': quality_verdict([x for x in b['quality'] if x['variant'] == 'stock']),
    }
    if any(not v['checks'] or any(value for key, value in v.items() if key != 'checks') for v in checks.values()):
        raise ValueError('Typed validity regression: ' + repr(checks))
    for treatment in ('patched-g0', 'patched-g1'):
        for result in r['treatments'][treatment].values():
            if result['errors'] or result['missing_pixels']:
                raise ValueError('Original rendering regression')
    errors = sum(x['summary']['errors'] for x in b['blocks'])
    errors_by_variant = {v: sum(x['summary']['errors'] for x in b['blocks'] if x['variant'] == v)
                         for v in ('stock', 'both')}
    if errors_by_variant['both'] or any(x['errors'] for x in f['profiles'] if x['variant'] == 'both'):
        raise ValueError('Optimized performance/profile request errors')
    failed_requests = []
    blocks_by_id = {x['id']: x for x in b['blocks']}
    with gzip.open(a.performance/'requests.jsonl.gz', 'rt') as stream:
        for line in stream:
            block = json.loads(line)
            meta = blocks_by_id[block['block']]
            for row in block['rows']:
                if row.get('error'):
                    failed_requests.append(dict(row, **{key: meta[key] for key in
                        ('replicate', 'round', 'variant', 'profile', 'concurrency')}))
    cases = [case_timings(b['blocks'], kind, angle) for kind in KINDS for angle in (0, 30)]
    requests = sum(x['summary']['requests'] for x in b['blocks'])
    reps = len({x['replicate'] for x in b['blocks']})
    verdict = dict(baseline_commit=BASELINE, typed=checks, rendering_passed=True,
                   timed_requests=requests, timed_errors=errors, timed_errors_by_variant=errors_by_variant,
                   failed_requests=failed_requests, fresh_jvm_pairs=reps, cases=cases)
    a.output.mkdir(parents=True, exist_ok=True)
    for name in ('quality', 'performance', 'rendering'):
        public = json.loads(json.dumps(data[name]))
        if name == 'rendering':
            for row in public['cache']:
                row.pop('url', None)
        probe.write_json(a.output/f'mask-optimized-{name}.json', public)
    probe.write_json(a.output/'mask-optimized-profile.json', dict(
        profiles=f['profiles'], patch_build=f['patch_build'], baseline_patch_build=f['baseline_patch_build'],
        environment=f['environment'], runtime=f['runtime'], baseline_runtime=f['baseline_runtime']))
    probe.write_json(a.output/'mask-optimized-verdict.json', verdict)
    shutil.copyfile(a.performance/'requests.jsonl.gz', a.output/'mask-optimized-requests.jsonl.gz')
    lines = ['# Mask processing optimization', '',
        'Branch: `codex/mask-performance`, based on the correct combined candidate '
        f'[`{BASELINE[:7]}`](https://github.com/AShapira/geoserver-affine-fix/commit/{BASELINE}). '
        '**Experimental; not merged to main or submitted upstream.**', '',
        '## What changed', '',
        '- NoData validity is calculated lazily into a byte image using direct buffer writes. A primitive range test replaces '
        'the generic range lookup, boxed values, temporary band images and band reduction. '
        'A pixel remains valid when any source band is valid; NaN and endpoint inclusivity are preserved.',
        '- Nearest-neighbor binary affine sampling reads packed BYTE/USHORT/INT bits directly when there is '
        'no additional ROI or NoData. Other interpolation and validity paths retain their existing implementation.',
        '- A synthetic footprint mask is omitted only if there is no NoData or existing ROI and every corner '
        'of the full request maps at least one source pixel inside the reader-selected image. '
        'Boundary tiles keep their masks; RGBA keeps its intrinsic alpha.',
        '- Existing ROI and NoData masks still intersect. Redundant intersection with a full-image rectangle is avoided.', '',
        'The code keeps the combined candidate’s precision, pixel-center bounds and zero-outside-mask fixes. '
        'It does not change the source TIFFs, output sampling, validity tolerances or output resolution.', '',
        '## Validity', '',
        f'**{checks["optimized"]["checks"]:,} optimized image checks**, repeated on '
        f'**{checks["paired_optimized"]["checks"]:,} images** in the paired benchmark: '
        '**zero missing pixels, spurious opaque pixels, alpha/color mismatches or response errors**. '
        f'The correct baseline also passes {checks["paired_baseline"]["checks"]:,} checks with the same oracle.', '',
        'Twenty fixtures cover RGB, native RGBA (including partial alpha), four-band UInt16 and Float32 '
        'numeric/NaN NoData; north-up/30° grids; base images/nearest overviews; gutters 0/1. '
        'Expected pixels come from the independent inverse-transform oracle. Tolerances remain '
        '2/255 color and 1/255 alpha, with no footprint erosion.', '',
        'The separate 14-fixture grayscale reproduction includes negative rotation, 45°/75° and shear. '
        'Patched WMS and GWC have zero missing pixels and response errors at both gutters 0 and 1. '
        'That older oracle measures missing coverage, not full color/alpha equality.', '',
        'Direct Java regressions exercise six sample storage types, one/three/four bands, NaN, infinities, '
        'unsigned values, open/closed ranges, nonzero image origins and tile offsets. Additional tests '
        'check packed-bit offsets/row padding, the conservative interior guard, and all existing '
        '32,448 clipping cases and precision/edge regressions. The pinned official-image build, '
        'Python build/oracle/report checks and JavaScript adapter checks pass.', '',
        '## Performance against the correct baseline', '',
        f'**{requests:,} timed requests, {reps} fresh JVM pairs**. Response errors: '
        f'**optimized {errors_by_variant["both"]}, baseline {errors_by_variant["stock"]}**. Three rounds per pair, '
        '1/6 clients, WMS/GWC MISS/GWC HIT, balanced variant order. Both variants run the same pinned '
        'official GeoServer 3.0.2 image with 2 CPUs, 6 GiB container memory and a 2 GiB Java heap. '
        'Profiling and other experiment loads run separately from timings.', '',
        'The table reports the median across JVM pairs of each pair’s median fixture latency across '
        'three rounds and base/overview variants, for single-client WMS. A positive reduction means faster. '
        'Reduction is computed within each pair before taking the median, so it can differ from the ratio of the displayed medians. '
        'The range shows the three paired reductions, not a statistical confidence interval. '
        'North-up controls do not use the new GeoTools mask path.', '',
        '| Case | Rotation | Correct baseline ms | Optimized ms | Median reduction | Range across JVM pairs |',
        '|---|---:|---:|---:|---:|---:|']
    for c in cases:
        reductions = [x['reduction_percent'] for x in c['replicates']]
        lines.append(f'| {c["kind"]} | {c["angle"]}° | {c["baseline_ms"]:.2f} | '
                     f'{c["optimized_ms"]:.2f} | {c["median_reduction_percent"]:.1f}% | '
                     f'{min(reductions):.1f}% to {max(reductions):.1f}% |')
    lines += ['', 'Across all 20 fixtures (north-up and rotated mixed), medians of block measurements:', '',
        '| Route | Clients | Baseline ms | Optimized ms | Baseline req/s | Optimized req/s | Baseline CPU ms/request | Optimized CPU ms/request |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for profile in ('wms', 'gwc-miss', 'gwc-hit'):
        for concurrency in (1, 6):
            grouped = {v: [x for x in b['blocks'] if x['profile'] == profile and x['concurrency'] == concurrency
                          and x['variant'] == v] for v in ('stock', 'both')}
            med = {v: np.median([x['summary']['median_ms'] for x in bs]) for v, bs in grouped.items()}
            rps = {v: np.median([x['summary']['successful_requests_per_second'] for x in bs]) for v, bs in grouped.items()}
            cpu = {v: [x['cpu_ms_per_request'] for x in bs if 'cpu_ms_per_request' in x]
                   for v, bs in grouped.items()}
            cpu = {v: f'{np.median(values):.2f}' if values else 'unavailable' for v, values in cpu.items()}
            lines.append(f'| {profile} | {concurrency} | {med["stock"]:.2f} | {med["both"]:.2f} | '
                         f'{rps["stock"]:.1f} | {rps["both"]:.1f} | '
                         f'{cpu["stock"]} | {cpu["both"]} |')
    if failed_requests:
        lines += ['', '**Baseline failures are retained.** Their cause is not established; this optimization '
            'is not claimed to fix them. Failed responses remain in request/error counts and reduce successful '
            'throughput; latency summaries include successful responses only.', '',
            '| Variant | Replicate | Round | Route | Clients | Fixture | Tile | Error |',
            '|---|---:|---:|---|---:|---|---|---|']
        for row in failed_requests:
            lines.append(f'| {row["variant"]} | {row["replicate"]} | {row["round"]} | {row["profile"]} | '
                         f'{row["concurrency"]} | {row["name"]} | {row["tile"]} | {row["error"]} |')
    lines += ['', 'GWC HIT bypasses rendering; differences there measure cache/HTTP noise, not mask speed. '
        'WMS timings use opaque output, while the separate validity checks use transparent output.', '',
        '## Why it improves', '',
        'The baseline repeatedly applies general-purpose range lookup and image-combination operations '
        'to construct a mask. The replacement writes the same validity decision directly into a byte buffer '
        'and stops scanning bands as soon as one is valid. ImageN performs the final binarization. Interior tiles without NoData or ROI avoid '
        'constructing and transforming a footprint mask. Packed affine sampling avoids a boxed copy '
        'of the source mask. These changes reduce work while retaining validity at edges and holes.', '',
        'Separate JFR profiles use the same rotated workload at six clients after warmup. Allocation '
        'figures below are sampled estimates, not exact allocation accounting or retained heap size.', '',
        '| Variant | Completed requests | Errors | Sampled allocation MiB/request | Execution samples |',
        '|---|---:|---:|---:|---:|']
    for profile in f['profiles']:
        label = 'Correct baseline' if profile['variant'] == 'stock' else 'Optimized'
        lines.append(f'| {label} | {profile["completed_requests"]:,} | {profile["errors"]} | '
                     f'{profile["estimated_allocation_bytes_per_request"]/2**20:.2f} | '
                     f'{profile["events"].get("jdk.ExecutionSample", 0):,} |')
    allocations = {x['variant']: x['estimated_allocation_bytes_per_request'] for x in f['profiles']}
    if allocations.get('stock') and 'both' in allocations:
        lines += ['', f'Sampled allocation per request falls by {100 * (1 - allocations["both"] / allocations["stock"]):.1f}%. '
            'The optimized profile still spends substantial CPU time reading and testing NoData samples; '
            'these results do not establish a maximum possible speedup.']
    lines += ['', 'See the [profile summary](mask-optimized-profile.json) for leaf and inclusive stacks. '
        'Inclusive frame counts overlap and must not be added as CPU percentages. '
        'These profiles support the mechanism; they do not isolate the contribution of each optimization.', '',
        '## Scope and evidence', '',
        'The results apply to this synthetic, nearest-neighbor, same-CRS workload on Linux/WSL. '
        'They are not a throughput guarantee for production data. Arbitrary reprojection, '
        'bilinear/bicubic rendering, projection-domain clipping, real ImageMosaic datasets and all TIFF '
        'layouts still need upstream testing. Direct multi-band NoData unit tests do not replace '
        'end-to-end tests of every GeoServer style. The finite scanline precision limit is unchanged.', '',
        '[Validity](mask-optimized-quality.json) · [Rendering](mask-optimized-rendering.json) · '
        '[Performance](mask-optimized-performance.json) · [Request timings](mask-optimized-requests.jsonl.gz) · '
        '[Verdict](mask-optimized-verdict.json) · [Profile](mask-optimized-profile.json)', '',
        'In raw files, `stock` is the **correct patched baseline**, and `both` is the **optimized candidate**. '
        'The baseline lock and both build manifests identify the exact libraries. JARs, TIFFs, '
        'credentials, JFR recordings and raw image responses remain ignored.', '',
        'Per-pixel and batched direct one-bit NoData outputs were also tried. Preliminary timings favored '
        'the byte intermediate, so the final implementation retains ImageN’s '
        '[ROI binarization](https://github.com/eclipse-imagen/imagen/blob/0.9.3/modules/core/src/main/java/org/eclipse/imagen/ROI.java). '
        'Those exploratory runs are not included in the final paired results.', '',
        '## Reproduce', '', '```bash',
        'git switch codex/mask-performance',
        'git worktree add --detach /tmp/affine-correct-baseline ' + BASELINE,
        '(cd /tmp/affine-correct-baseline && uv run python -m affine_fix.build --output .runs/patch)',
        'uv run python -m affine_fix.typed_suite --root .runs/optimized-quality --quality-only --variants both',
        'uv run python -m affine_fix.typed_suite --root .runs/optimized-performance --replicates 3 \\',
        '  --patch .runs/optimized-quality/patch \\',
        '  --baseline-patch /tmp/affine-correct-baseline/.runs/patch \\',
        '  --baseline-lock /tmp/affine-correct-baseline/runtime/lock.json',
        'uv run affine-reproduce --root .runs/optimized-rendering',
        'uv run python -m affine_fix.typed_suite --root .runs/optimized-profile --profile-only \\',
        '  --patch .runs/optimized-quality/patch \\',
        '  --baseline-patch /tmp/affine-correct-baseline/.runs/patch \\',
        '  --baseline-lock /tmp/affine-correct-baseline/runtime/lock.json',
        'uv run python -m affine_fix.mask_report --quality .runs/optimized-quality \\',
        '  --performance .runs/optimized-performance --rendering .runs/optimized-rendering \\',
        '  --profile .runs/optimized-profile', '```', '']
    (a.output/'mask-optimized.md').write_text('\n'.join(lines))
    print(a.output/'mask-optimized.md')


if __name__ == '__main__':
    main()
