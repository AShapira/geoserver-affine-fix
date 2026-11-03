"""Benchmark accounting, local cgroup measurements and separate JFR profiles."""
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import platform

import numpy as np

from . import lab, probe


def summary(rows, elapsed):
    good = [r for r in rows if not r.get('error')]
    values = [r['seconds'] * 1000 for r in good]
    return {'requests': len(rows), 'errors': len(rows) - len(good), 'elapsed_seconds': elapsed,
            'median_ms': float(np.median(values)) if values else None,
            'p95_ms': float(np.percentile(values, 95)) if values else None,
            'successful_requests_per_second': len(good) / elapsed,
            'cache': dict(Counter(r['cache'] or 'none' for r in good)),
            'mean_bytes': float(np.mean([r['bytes'] for r in good])) if good else None,
            'by_fixture': {name: summary([r for r in rows if r['name'] == name], elapsed)
                           for name in sorted({r['name'] for r in rows})} if len({r['name'] for r in rows}) > 1 else {}}


def cgroup_path(state):
    # A remote engine's PID must never be interpreted as a local host PID.
    if '--connection' in state['engine'] or os.environ.get('CONTAINER_HOST') or os.environ.get('CONTAINER_CONNECTION'):
        return None
    if state['engine'][0] != 'podman':
        return None
    remote = lab.call(state['engine'], 'info', '--format', '{{.Host.ServiceIsRemote}}', check=False)
    if remote.returncode or remote.stdout.strip() != b'false':
        return None
    info = lab.owned_container(state)
    try:
        lines = Path(f'/proc/{info["State"]["Pid"]}/cgroup').read_text().splitlines()
        for line in lines:
            if line.startswith('0::') and state['container_id'] in line:
                path = Path('/sys/fs/cgroup') / line[3:].lstrip('/')
                if (path / 'cpu.stat').is_file():
                    return path
    except (OSError, KeyError):
        pass
    return None


def resources(path):
    if path is None:
        return {}
    cpu = dict(line.split() for line in (path / 'cpu.stat').read_text().splitlines())
    return {'cpu_usec': int(cpu['usage_usec']), 'throttled_usec': int(cpu.get('throttled_usec', 0)),
            'memory_current': int((path / 'memory.current').read_text()),
            'memory_peak': int((path / 'memory.peak').read_text())}


def environment():
    cpu = 'unavailable'
    memory = None
    if Path('/proc/cpuinfo').exists():
        cpu = next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines()
                    if s.startswith('model name')), cpu)
    if Path('/proc/meminfo').exists():
        memory = int(Path('/proc/meminfo').read_text().splitlines()[0].split()[1]) * 1024
    return {'cpu_model': cpu, 'logical_cpus': os.cpu_count(), 'total_memory_bytes': memory,
            'platform': platform.system(), 'kernel': platform.release(), 'machine': platform.machine(),
            'python': platform.python_version()}


def frames(event):
    trace = event['values'].get('stackTrace') or {}
    result = []
    for frame in trace.get('frames', []):
        method = frame['method']
        result.append(method['type']['name'].replace('/', '.') + '.' + method['name'])
    return result


def jfr_summary(events, requests):
    execution, allocations = Counter(), Counter()
    count = Counter()
    leaf_execution, leaf_allocations = Counter(), Counter()
    crop_samples = 0
    crop_weight = 0
    total_weight = 0
    for event in events:
        kind = event['type']
        count[kind] += 1
        stack = frames(event)
        crop = any('CoverageCrop.' in f or 'GridCoverageReaderHelper.cropCoverage' in f for f in stack)
        if kind == 'jdk.ExecutionSample':
            if stack: leaf_execution[stack[0]] += 1
            execution.update(set(stack))  # Inclusive stack samples, not additive CPU percentages.
            crop_samples += int(crop)
        elif kind == 'jdk.ObjectAllocationSample':
            weight = event['values']['weight']
            if stack: leaf_allocations[stack[0]] += weight
            total_weight += weight
            crop_weight += weight if crop else 0
            for method in set(stack):
                allocations[method] += weight
    return {'events': dict(count), 'completed_requests': requests,
            'allocation_sample_weight_bytes': total_weight,
            'estimated_allocation_bytes_per_request': total_weight / max(1, requests),
            'crop_execution_samples': crop_samples, 'crop_allocation_sample_weight_bytes': crop_weight,
            'leaf_execution_stacks': leaf_execution.most_common(50),
            'leaf_allocation_stacks': leaf_allocations.most_common(50),
            'inclusive_execution_stacks': execution.most_common(50),
            'inclusive_allocation_stacks': allocations.most_common(50)}


def start_profile(state):
    engine, container = state['engine'], state['container_id']
    lab.owned_container(state)
    listing = lab.call(engine, 'exec', container, 'jcmd', '-l').stdout.decode()
    candidates = [line.split()[0] for line in listing.splitlines() if 'org.apache.catalina.startup.Bootstrap' in line]
    if len(candidates) != 1:
        raise RuntimeError('Could not identify the isolated Tomcat JVM for profiling')
    pid = candidates[0]
    lab.call(engine, 'exec', container, 'jcmd', pid, 'JFR.start', 'name=affine', 'settings=profile',
             'jdk.ExecutionSample#period=10ms', 'filename=/tmp/affine.jfr')
    return pid


def finish_profile(state, pid, directory, requests):
    engine, container = state['engine'], state['container_id']
    lab.call(engine, 'exec', container, 'jcmd', pid, 'JFR.stop', 'name=affine')
    directory.mkdir(parents=True, exist_ok=True)
    lab.call(engine, 'cp', container + ':/tmp/affine.jfr', str(directory / 'recording.jfr'))
    raw = lab.call(engine, 'exec', container, 'jfr', 'print', '--json', '--stack-depth', '32',
                   '--events', 'jdk.ExecutionSample,jdk.ObjectAllocationSample,jdk.GarbageCollection,jdk.GCPhasePause',
                   '/tmp/affine.jfr').stdout
    with gzip.open(directory / 'events.json.gz', 'wb') as output:
        output.write(raw)
    result = jfr_summary(json.loads(raw)['recording']['events'], requests)
    probe.write_json(directory / 'summary.json', result)
    return result
