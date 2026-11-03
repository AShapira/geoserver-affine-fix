"""Export measured benchmark results without credentials, URLs or raw recordings."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import re
import shutil

import numpy as np

from . import probe
from .benchmark_metrics import frames
from .benchmark import VARIANTS

KEYS = ('suite', 'profile', 'gutter', 'concurrency', 'size', 'interpolation')
METRICS = ('median_ms', 'p95_ms', 'successful_requests_per_second', 'cpu_ms_per_request', 'mean_bytes')


def jfr_events(source, chunk_size=65536):
    """Stream the pinned JDK's events array; its expanded JSON can be gigabytes."""
    buffer = ''
    header = re.compile(r'^\s*\{\s*"recording"\s*:\s*\{\s*"events"\s*:\s*\[')
    while not (match := header.match(buffer)):
        chunk = source.read(chunk_size)
        if not chunk or len(buffer) > 1048576:
            raise ValueError('Invalid JFR JSON header')
        buffer += chunk
    buffer = buffer[match.end():]
    decoder = json.JSONDecoder()
    while True:
        buffer = buffer.lstrip()
        while not buffer:
            buffer = source.read(chunk_size).lstrip()
            if not buffer:
                raise ValueError('Truncated JFR events')
        if buffer.startswith(']'):
            tail = buffer + source.read()
            if not re.fullmatch(r'\]\s*\}\s*\}\s*', tail):
                raise ValueError('Invalid JFR JSON trailer')
            return
        while True:
            try:
                event, end = decoder.raw_decode(buffer)
                break
            except json.JSONDecodeError:
                chunk = source.read(chunk_size)
                if not chunk:
                    raise ValueError('Truncated or invalid JFR event') from None
                buffer += chunk
        yield event
        buffer = buffer[end:].lstrip()
        while not buffer:
            buffer = source.read(chunk_size).lstrip()
            if not buffer:
                raise ValueError('Truncated JFR events')
        if buffer.startswith(','):
            buffer = buffer[1:]
        elif not buffer.startswith(']'):
            raise ValueError('Invalid JFR event separator')


def value(block, metric, fixture=None):
    if metric == 'cpu_ms_per_request':
        return block.get(metric) if fixture is None else None
    source = block['summary'] if fixture is None else block['summary']['by_fixture'].get(fixture, {})
    return source.get(metric)


def aggregate(blocks, metric, fixture=None):
    grouped = defaultdict(list)
    for block in blocks:
        number = value(block, metric, fixture)
        if number is not None:
            grouped[block['replicate']].append(number)
    replicates = {str(k): float(np.median(v)) for k, v in sorted(grouped.items())}
    numbers = list(replicates.values())
    return {'median': float(np.median(numbers)), 'min': min(numbers), 'max': max(numbers),
            'replicates': replicates} if numbers else None


def paired_change(stock, treatment, metric, fixture=None):
    """Pair independent JVM replicates; requests and rounds are not extra replicates."""
    a, b = aggregate(stock, metric, fixture), aggregate(treatment, metric, fixture)
    if a is None or b is None:
        return None
    if set(a['replicates']) != set(b['replicates']):
        raise ValueError('Unmatched independent replicates')
    changes = {k: (b['replicates'][k] / v - 1) * 100 for k, v in a['replicates'].items() if v != 0}
    numbers = list(changes.values())
    return {'median_percent': float(np.median(numbers)), 'min_percent': min(numbers),
            'max_percent': max(numbers), 'replicates_percent': changes} if numbers else None


def conditions(blocks):
    groups = defaultdict(list)
    for block in blocks:
        if block['suite'] != 'soak':
            groups[tuple(block[k] for k in KEYS)].append(block)
    result = []
    for key, items in sorted(groups.items()):
        by_variant = {v: [b for b in items if b['variant'] == v] for v in VARIANTS}
        if any(not blocks for blocks in by_variant.values()):
            raise ValueError('Incomplete variant comparison')
        row = dict(zip(KEYS, key))
        row['variants'] = {}
        for variant, blocks in by_variant.items():
            data = {'requests': sum(b['summary']['requests'] for b in blocks),
                    'errors': sum(b['summary']['errors'] for b in blocks),
                    'metrics': {m: aggregate(blocks, m) for m in METRICS},
                    'by_fixture': {name: {m: aggregate(blocks, m, name) for m in ('median_ms', 'p95_ms', 'mean_bytes')}
                                   for name in sorted({n for b in blocks for n in b['summary']['by_fixture']})}}
            if variant != 'stock':
                data['paired_change_vs_stock'] = {m: paired_change(by_variant['stock'], blocks, m) for m in METRICS}
            row['variants'][variant] = data
        result.append(row)
    return result


def quality_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['variant'], row['suite'], row['gutter'])].append(row)
    return [dict(variant=k[0], suite=k[1], gutter=k[2], requests=len(items),
                 errors=sum(bool(i.get('error')) for i in items),
                 images_with_missing_pixels=sum(i.get('missing_pixels', 0) > 0 for i in items),
                 missing_pixels=sum(i.get('missing_pixels', 0) for i in items))
            for k, items in sorted(groups.items())]


def focused_profile(events):
    """Retain rendering evidence that broad inclusive servlet stacks can obscure."""
    leaf, relevant, allocation, classes = Counter(), Counter(), Counter(), Counter()
    roi_samples = roi_weight = 0
    for event in events:
        stack = frames(event)
        methods = {m for m in stack if any(part in m for part in
                   ('CoverageCrop', 'GridCoverageReaderHelper', 'ROI', 'CropOpImage',
                    'AffineNearest', 'AffineGeneral', 'SingleImageMosaic', 'AlgebraOpImage',
                    'RasterAccessor', 'Warp'))}
        roi = any('ROI' in m for m in stack)
        if event['type'] == 'jdk.ExecutionSample':
            if stack:
                leaf[stack[0]] += 1
            relevant.update(methods)
            roi_samples += int(roi)
        elif event['type'] == 'jdk.ObjectAllocationSample':
            weight = event['values']['weight']
            roi_weight += weight if roi else 0
            for method in methods:
                allocation[method] += weight
            classes[event['values']['objectClass']['name'].replace('/', '.')] += weight
    return {'execution_leaf_methods': leaf.most_common(30),
            'rendering_inclusive_execution_stacks': relevant.most_common(),
            'rendering_inclusive_allocation_stacks': allocation.most_common(),
            'allocation_classes': classes.most_common(30),
            'roi_execution_samples': roi_samples, 'roi_allocation_sample_weight_bytes': roi_weight}


def chart(data, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), layout='constrained')
    colors = ['#7b8994', '#4387ad', '#ab8c53', '#27856a']
    for ax, profile, title in zip(axes, ('wms', 'gwc-miss', 'gwc-hit'),
                                 ('Direct WMS', 'GWC cache MISS', 'GWC cache HIT'), strict=True):
        group = next(r for r in data if r['suite'] == 'core' and r['profile'] == profile
                     and r['gutter'] == 1 and r['concurrency'] == 1)
        stats = [group['variants'][v]['metrics']['median_ms'] for v in VARIANTS]
        medians = [s['median'] for s in stats]
        ax.bar(range(4), medians, color=colors, width=.68,
               yerr=[[s['median'] - s['min'] for s in stats], [s['max'] - s['median'] for s in stats]], capsize=4)
        ax.set_xticks(range(4), ['Stock', 'GeoTools\nonly', 'ImageN\nonly', 'Both'])
        ax.set_title(title, fontsize=12, weight='bold')
        ax.set_ylabel('Median response time (ms)')
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(s['max'] for s in stats) * 1.22)
        for x, y in enumerate(medians):
            ax.text(x, stats[x]['max'] + ax.get_ylim()[1] * .035, f'{y:.2f}', ha='center', fontsize=10)
    fig.suptitle('Official GeoServer 3.0.2 · same requests, different source corrections', fontsize=14, weight='bold')
    fig.supxlabel('One client · 256 × 256 tile (WMS adds a 1 px gutter) · bars: median across fresh JVMs; whiskers: range', fontsize=9)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160, facecolor='white')
    plt.close(fig)


def table(group):
    lines = ['| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for variant in VARIANTS:
        data = group['variants'][variant]
        m = data['metrics']
        def fmt(metric):
            return f'{m[metric]["median"]:.2f}' if m[metric] else 'unavailable'
        latency = m['median_ms']
        span = f'{latency["min"]:.2f}–{latency["max"]:.2f}' if latency else 'unavailable'
        lines.append(f'| {variant} | {fmt("median_ms")} | {span} | {fmt("p95_ms")} | '
                     f'{fmt("successful_requests_per_second")} | {fmt("cpu_ms_per_request")} | {data["errors"]} |')
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('docs'))
    args = parser.parse_args()
    raw = json.loads((args.run / 'result.json').read_text())
    if not raw.get('complete') or not raw.get('source_fixtures_unchanged'):
        raise RuntimeError('Refusing to publish an incomplete or mutated-fixture run')
    output = args.output / 'performance'
    output.mkdir(parents=True, exist_ok=True)
    data = conditions(raw['blocks'])
    public = {key: raw[key] for key in ('started_utc', 'finished_utc', 'runtime', 'environment', 'replicates',
        'rounds', 'profile_seconds', 'soak_seconds', 'container_cpu_limit', 'container_memory_gib', 'heap_max_gib',
        'benchmark_source_sha256', 'workloads', 'fixture_sha256', 'source_fixtures_unchanged',
        'measured_requests', 'measured_errors', 'servers', 'profiles')}
    public.update(conditions=data, quality=quality_summary(raw['quality']), blocks=raw['blocks'])
    public['report_source_sha256'] = probe.digest(Path(__file__))
    for variant, profile in public['profiles'].items():
        with gzip.open(args.run / 'profiles' / variant / 'events.json.gz', 'rt') as source:
            profile.update(focused_profile(jfr_events(source)))
    public['request_samples_sha256'] = probe.digest(args.run / 'requests.jsonl.gz')
    probe.write_json(output / 'results.json', public)
    shutil.copyfile(args.run / 'requests.jsonl.gz', output / 'requests.jsonl.gz')
    with gzip.open(output / 'quality.json.gz', 'wt') as target:
        json.dump(raw['quality'], target, allow_nan=False)
    fields = ['id', 'replicate', 'round', *KEYS, 'variant', 'requests', 'errors', 'elapsed_seconds', *METRICS]
    with (output / 'blocks.csv').open('w', newline='') as target:
        writer = csv.DictWriter(target, fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for b in raw['blocks']:
            writer.writerow(dict(b, **{k: v for k, v in b['summary'].items() if k != 'by_fixture'}))
    lines = ['# Generated performance measurements', '',
        f'Completed {raw["finished_utc"]}. {raw["measured_requests"]:,} timed requests; {raw["measured_errors"]:,} errors.', '',
        f'{raw["replicates"]} independent JVMs per variant; {raw["rounds"]} measured core rounds per JVM. '
        'For each JVM we take the median of its block statistics, then report the median and full range across JVMs. '
        'The p95 column is the same aggregation of block p95 values, not a pooled-request percentile. '
        'The range is not a confidence interval. CPU includes the entire server cgroup.', '',
        'First-use means the first workload after catalog publication, without an explicit renderer warmup; '
        'it does not mean cold operating-system disk cache. Soak blocks are in the downloadable data, '
        'but are excluded from independent-replicate comparisons.', '',
        '[Method and interpretation](../performance.md) · [Full results](results.json) · '
        '[Block CSV](blocks.csv) · [Request samples](requests.jsonl.gz) · [Pixel checks](quality.json.gz)', '']
    for group in data:
        lines += [f'## {group["suite"]}: {group["profile"]}, gutter {group["gutter"]}, '
                  f'{group["concurrency"]} client{"s" if group["concurrency"] != 1 else ""}, '
                  f'{group["size"]} px, {group["interpolation"]}', '']
        lines += table(group) + ['']
    (output / 'measured.md').write_text('\n'.join(lines))
    chart(data, args.output / 'assets/performance.png')
    print('Published sanitized performance evidence:', output)


if __name__ == '__main__':
    main()
