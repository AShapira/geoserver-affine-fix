"""Measure official GeoServer with stock, individual fixes and both fixes.

Run servers sequentially under load, with paired request orders and independent
fresh JVM/catalog replicates. Raw local evidence is separate from public reports.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import io
import json
import os
from pathlib import Path
import random
import struct
import threading
import time

from PIL import Image
import requests

from . import benchmark_metrics as bm
from . import benchmark_workloads as bw
from . import lab, probe
from .reproduce import command

VARIANTS = ('stock', 'geotools', 'imagen', 'both')
PROFILES = ('wms', 'gwc-miss', 'gwc-hit')


def request(session, base, job, profile, gutter, size=256, interpolation='nearest neighbor', keep_image=False):
    """Time receipt of the complete body; validate it outside the latency timer."""
    tile = job['tile']
    if profile == 'wms':
        bbox = probe.tile(*tile)
        res = (bbox[2] - bbox[0]) / size
        bbox = [bbox[0] - gutter * res, bbox[1] - gutter * res,
                bbox[2] + gutter * res, bbox[3] + gutter * res]
        expected_size = size + 2 * gutter
        params = probe.wms(job['name'], bbox, interpolation, expected_size, expected_size)
        path = '/wms'
    else:
        expected_size = 256
        params = {'SERVICE': 'WMTS', 'VERSION': '1.0.0', 'REQUEST': 'GetTile',
                  'LAYER': f'{probe.WS}:{job["name"]}', 'STYLE': '', 'FORMAT': 'image/png',
                  'TILEMATRIXSET': probe.GRID, 'TILEMATRIX': f'{probe.GRID}:{tile[0]}',
                  'TILECOL': tile[1], 'TILEROW': tile[2]}
        path = '/gwc/service/wmts'
    row = {'name': job['name'], 'tile': tile}
    start = time.perf_counter()
    try:
        response = session.get(base + path, params=params, timeout=120)
        row.update(seconds=time.perf_counter() - start, status=response.status_code,
                   bytes=len(response.content), cache=response.headers.get('geowebcache-cache-result'))
        data = response.content
        if (not response.ok or not response.headers.get('Content-Type', '').lower().startswith('image/png')
                or len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n'
                or struct.unpack('>II', data[16:24]) != (expected_size, expected_size)):
            row['error'] = 'invalid_image_response'
        elif profile != 'wms' and row['cache'] != profile.split('-')[1].upper():
            row['error'] = 'unexpected_cache_state'
        if keep_image and not row.get('error'):
            image = Image.open(io.BytesIO(data))
            image.load()
            if profile == 'wms' and gutter:
                image = image.crop((gutter, gutter, gutter + size, gutter + size))
            return row, image
    except requests.RequestException as error:
        row.update(seconds=time.perf_counter() - start, error=type(error).__name__)
    return (row, None) if keep_image else row


class Runner:
    def __init__(self, args, entries, jobs):
        self.args, self.entries, self.jobs = args, {e['name']: e for e in entries}, jobs
        self.states, self.sessions, self.cgroups = {}, {}, {}
        self.pools = {c: ThreadPoolExecutor(max_workers=c) for c in (1, 6, 12)}
        self.local = threading.local()
        self.blocks, self.quality, self.profiles, self.servers = [], [], {}, []
        self.block_index = 0

    def select(self, variant):
        state = self.states[variant]
        probe.BASE, probe.FIXTURE_ROOT = state['url'], self.args.root / 'fixtures'
        probe.SERVER_FIXTURE_DIR = state['server_fixture_dir']
        return self.sessions[variant]

    def perform(self, variant, jobs, profile, gutter, concurrency, size=256, interpolation='nearest neighbor'):
        state = self.states[variant]
        def worker(job):
            if not hasattr(self.local, 'sessions'):
                self.local.sessions = {}
            key = state['container_id']
            if key not in self.local.sessions:
                session = requests.Session()
                session.auth = self.sessions[variant].auth
                self.local.sessions[key] = session
            return request(self.local.sessions[key], state['url'], job, profile, gutter, size, interpolation)
        return list(self.pools[concurrency].map(worker, jobs))

    def clear(self, variant, jobs):
        session = self.select(variant)
        for name in sorted({j['name'] for j in jobs}):
            probe.truncate(session, name, 14, 24)

    def configure(self, gutter, jobs):
        for variant in self.states:
            session = self.select(variant)
            for name in sorted({j['name'] for j in jobs}):
                probe.cache_config(session, name, gutter, 1)
            self.clear(variant, jobs)

    def block(self, variant, jobs, *, replicate, round, suite, profile='wms', gutter=1,
              concurrency=1, size=256, interpolation='nearest neighbor', prepare=True):
        if prepare and profile == 'gwc-miss':
            self.clear(variant, jobs)
        elif prepare and profile == 'gwc-hit':
            # The priming pass can contain either MISS or HIT; neither enters timings.
            priming = self.perform(variant, jobs, 'gwc-hit', gutter, concurrency)
            if any(r.get('error') not in (None, 'unexpected_cache_state') for r in priming):
                raise RuntimeError('GWC priming failed')
        before = bm.resources(self.cgroups[variant])
        start = time.perf_counter()
        rows = self.perform(variant, jobs, profile, gutter, concurrency, size, interpolation)
        elapsed = time.perf_counter() - start
        after = bm.resources(self.cgroups[variant])
        block = {'id': self.block_index, 'replicate': replicate, 'round': round, 'suite': suite,
                 'variant': variant, 'profile': profile, 'gutter': gutter, 'concurrency': concurrency,
                 'size': size, 'interpolation': interpolation, 'summary': bm.summary(rows, elapsed),
                 'resources_before': before, 'resources_after': after,
                 'load_average': list(os.getloadavg()) if hasattr(os, 'getloadavg') else None}
        if before:
            block['cpu_ms_per_request'] = (after['cpu_usec'] - before['cpu_usec']) / 1000 / len(rows)
        with gzip.open(self.args.root / 'requests.jsonl.gz', 'at') as output:
            output.write(json.dumps({'block': self.block_index, 'rows': rows}, allow_nan=False) + '\n')
        with (self.args.root / 'blocks.jsonl').open('a') as output:
            output.write(json.dumps(block, allow_nan=False) + '\n')
        self.blocks.append(block)
        self.block_index += 1
        s = block['summary']
        print(f'{replicate=} {variant:8} {suite:12} {profile:8} g{gutter} c{concurrency:2} '
              f'{s["median_ms"]!s:18} ms; {s["successful_requests_per_second"]:.1f} req/s; '
              f'{s["errors"]} errors', flush=True)
        return block

    def paired(self, jobs, **kwargs):
        ordered = list(jobs)
        random.Random(1701 + kwargs['replicate'] * 1000 + kwargs['round'] * 100
                      + kwargs.get('gutter', 1) * 10 + kwargs.get('concurrency', 1)).shuffle(ordered)
        # Rotate start position and reverse direction, balancing which variant runs first.
        offset = (self.block_index // 4 + kwargs['replicate']) % 4
        order = VARIANTS[offset:] + VARIANTS[:offset]
        if (self.block_index // 4) % 2:
            order = tuple(reversed(order))
        for variant in order:
            self.block(variant, ordered, **kwargs)

    def start(self, replicate):
        order = VARIANTS[replicate % 4:] + VARIANTS[:replicate % 4]
        for variant in order:
            root = self.args.root / f'replicate-{replicate}' / variant
            state = lab.up(argparse.Namespace(root=root, fixtures=self.args.root / 'fixtures',
                engine=self.args.engine, connection=self.args.connection, port=self.args.port + VARIANTS.index(variant),
                pull=False, patch=None if variant == 'stock' else self.args.root / 'patch',
                components=variant, fixture_set='benchmark'))
            self.states[variant] = state
            self.cgroups[variant] = bm.cgroup_path(state)
            self.sessions[variant] = probe.session('admin', state['password_file'])
            s = self.select(variant)
            catalog = root / 'catalog'
            probe.snapshot(catalog, s)
            probe.publish(catalog, s)
            lock = lab.load_lock()
            hashes = {}
            for jar in lock['libraries']:
                value = lab.call(state['engine'], 'exec', state['container_id'], 'sha256sum',
                                 lock['library_directory'] + '/' + jar).stdout.decode().split()[0]
                hashes[jar] = value
            selected = lab.selected_libraries(lock, variant) if variant != 'stock' else {}
            build = json.loads((self.args.root / 'patch/build.json').read_text())
            expected = {jar: build['libraries'][jar]['patched_sha256'] if jar in selected else spec['sha256']
                        for jar, spec in lock['libraries'].items()}
            if hashes != expected:
                raise RuntimeError('Installed JARs do not match this ablation')
            self.servers.append({'replicate': replicate, 'variant': variant, 'installed_sha256': hashes,
                'image_id': state['image_id'], 'versions': json.loads((root / 'version.json').read_text()),
                'java': lab.call(state['engine'], 'exec', state['container_id'], 'java', '-version').stderr.decode(),
                'cgroup_measurement_available': self.cgroups[variant] is not None})

    def correctness(self, variant):
        session = self.select(variant)
        for suite in ('core', 'large', 'geometry'):
            for gutter in (0, 1):
                for job in self.jobs[suite]:
                    row, image = request(session, self.states[variant]['url'], job, 'wms', gutter, keep_image=True)
                    if image is not None:
                        ref, valid = bw.reference(self.entries[job['name']], job['tile'])
                        if not valid.all():
                            raise RuntimeError('Benchmark tile is not fully interior')
                        quality, _ = probe.metrics(image, ref, valid)
                        row.update(quality)
                    self.quality.append(dict(row, variant=variant, suite=suite, gutter=gutter))
        probe.write_json(self.args.root / 'quality.json', self.quality)

    def profile(self, variant):
        jobs = [j for j in self.jobs['core'] if j['name'] != 'rot0_base']
        pid = bm.start_profile(self.states[variant])
        start, count, errors = time.monotonic(), 0, 0
        while time.monotonic() - start < self.args.profile_seconds:
            rows = self.perform(variant, jobs, 'wms', 1, 6)
            count += len(rows)
            errors += sum(bool(r.get('error')) for r in rows)
        elapsed = time.monotonic() - start
        result = bm.finish_profile(self.states[variant], pid, self.args.root / 'profiles' / variant, count - errors)
        result.update(elapsed_seconds=elapsed, errors=errors, concurrency=6, gutter=1, suite='rotated_core')
        self.profiles[variant] = result
        print('Profile complete:', variant, count, 'requests', flush=True)

    def close_servers(self):
        failures = []
        for variant, state in list(self.states.items()):
            root = self.args.root / f'replicate-{self.current_replicate}' / variant
            try:
                lab.stop(state, root)
                lab.owned_container(state)
                lab.call(state['engine'], 'rm', state['container_id'])
                (root / 'lab.json').rename(root / 'removed-lab.json')
                del self.states[variant]
            except Exception as error:
                failures.append((variant, str(error)))
        if failures:
            raise RuntimeError('Lab cleanup failed: ' + repr(failures))

    def run(self):
        try:
            for replicate in range(self.args.replicates):
                self.current_replicate = replicate
                self.start(replicate)
                self.paired(self.jobs['core'], replicate=replicate, round=0, suite='first-use', gutter=0)
                for variant in VARIANTS:
                    for concurrency in (1, 6, 12):
                        for gutter in (0, 1):
                            rows = self.perform(variant, self.jobs['core'], 'wms', gutter, concurrency)
                            if any(r.get('error') for r in rows):
                                raise RuntimeError('Core warmup failed')
                for round in range(self.args.rounds):
                    for gutter in ((0, 1) if (replicate + round) % 2 == 0 else (1, 0)):
                        self.configure(gutter, self.jobs['core'])
                        for concurrency in ((1, 6, 12) if round % 2 == 0 else (12, 6, 1)):
                            for profile in PROFILES:
                                self.paired(self.jobs['core'], replicate=replicate, round=round, suite='core',
                                            gutter=gutter, concurrency=concurrency, profile=profile)
                self.configure(1, self.jobs['large'])
                for variant in VARIANTS:
                    self.perform(variant, self.jobs['large'], 'wms', 1, 6)
                for concurrency in (1, 6, 12):
                    for profile in PROFILES:
                        self.paired(self.jobs['large'], replicate=replicate, round=0, suite='large',
                                    concurrency=concurrency, profile=profile)
                for concurrency in (1, 6):
                    self.paired(self.jobs['geometry'], replicate=replicate, round=0, suite='geometry', concurrency=concurrency)
                    for interpolation in ('bilinear', 'bicubic'):
                        self.paired(self.jobs['control'], replicate=replicate, round=0, suite='interpolation',
                                    interpolation=interpolation, concurrency=concurrency)
                    for size in (512, 1024):
                        self.paired(self.jobs['control'], replicate=replicate, round=0, suite='output-size',
                                    size=size, concurrency=concurrency)
                if replicate == 0:
                    for variant in VARIANTS:
                        self.correctness(variant)
                    if self.args.profile_seconds:
                        for variant in VARIANTS:
                            self.profile(variant)
                if replicate == self.args.replicates - 1 and self.args.soak_seconds:
                    for variant in ('stock', 'both'):
                        start, round = time.monotonic(), 0
                        while time.monotonic() - start < self.args.soak_seconds:
                            self.block(variant, self.jobs['core'], replicate=replicate, round=round, suite='soak', concurrency=6)
                            round += 1
                self.close_servers()
        finally:
            for pool in self.pools.values():
                pool.shutdown()
            if self.states:
                self.close_servers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.runs/benchmark-3.0.2'))
    parser.add_argument('--engine', default='podman')
    parser.add_argument('--connection')
    parser.add_argument('--port', type=int, default=18106, help='First of four consecutive localhost ports')
    parser.add_argument('--pull', action='store_true')
    parser.add_argument('--replicates', type=int, default=3)
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--profile-seconds', type=int, default=30)
    parser.add_argument('--soak-seconds', type=int, default=120)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65532 and args.replicates >= 1 and args.rounds >= 1
            and args.profile_seconds >= 0 and args.soak_seconds >= 0):
        parser.error('Invalid port, count or duration')
    args.root = args.root.resolve()
    args.root.mkdir(parents=True, exist_ok=False)
    args.root.chmod(0o700)
    probe.FIXTURE_ROOT = None
    bw.fixtures(args.root / 'fixtures')
    entries = probe.verify(args.root / 'fixtures')
    hashes = {e['name']: e['sha256'] for e in entries}
    jobs = bw.workloads(entries)
    probe.write_json(args.root / 'workloads.json', jobs)
    build_args = ['--engine', args.engine, '--output', args.root / 'patch']
    if args.connection:
        build_args += ['--connection', args.connection]
    if args.pull:
        build_args += ['--pull']
    command(args.root / 'build.log', 'affine_fix.build', *build_args)
    runner = Runner(args, entries, jobs)
    result = {'started_utc': datetime.now(timezone.utc).isoformat(), 'runtime': lab.load_lock(),
              'environment': bm.environment(), 'replicates': args.replicates, 'rounds': args.rounds,
              'benchmark_source_sha256': {name: probe.digest(lab.ROOT / 'affine_fix' / name) for name in
                  ('benchmark.py', 'benchmark_metrics.py', 'benchmark_workloads.py', 'lab.py', 'probe.py')},
              'profile_seconds': args.profile_seconds, 'soak_seconds': args.soak_seconds,
              'container_cpu_limit': 2, 'container_memory_gib': 6, 'heap_max_gib': 2,
              'workloads': jobs, 'fixture_sha256': hashes, 'complete': False}
    probe.write_json(args.root / 'run.json', result)
    try:
        runner.run()
        probe.FIXTURE_ROOT = None
        if hashes != {e['name']: e['sha256'] for e in probe.verify(args.root / 'fixtures')}:
            raise RuntimeError('Source fixtures changed')
        result.update(complete=True, source_fixtures_unchanged=True)
    finally:
        result.update(finished_utc=datetime.now(timezone.utc).isoformat(), blocks=runner.blocks,
                      quality=runner.quality, profiles=runner.profiles, servers=runner.servers,
                      measured_requests=sum(b['summary']['requests'] for b in runner.blocks),
                      measured_errors=sum(b['summary']['errors'] for b in runner.blocks))
        probe.write_json(args.root / 'result.json', result)
    print('Completed:', result['measured_requests'], 'timed requests;', result['measured_errors'], 'errors', flush=True)


if __name__ == '__main__':
    main()
