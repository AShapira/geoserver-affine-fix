"""Run a controlled official GeoServer stock/patched comparison at gutters 0 and 1."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from . import lab, probe


def command(log, module, *args):
    with log.open('w') as output:
        result = subprocess.run([sys.executable, '-m', module, *map(str, args)], stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{module} failed; see {log}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.runs/geoserver-3.0.2'))
    parser.add_argument('--engine', default='podman')
    parser.add_argument('--connection')
    parser.add_argument('--port', type=int, default=18096)
    parser.add_argument('--pull', action='store_true')
    parser.add_argument('--quick', action='store_true', help='Interior subset; default includes footprint-edge cases')
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    root.chmod(0o700)
    logs = root / 'logs'
    logs.mkdir()
    fixtures = root / 'fixtures'
    probe.fixtures(fixtures)
    before = {e['name']: e['sha256'] for e in probe.verify(fixtures)}
    build_args = ['--engine', args.engine, '--output', root / 'patch']
    if args.connection:
        build_args += ['--connection', args.connection]
    if args.pull:
        build_args += ['--pull']
    print('Building matched source corrections...', flush=True)
    command(logs / 'build.log', 'affine_fix.build', *build_args)
    summaries = {}
    versions = {}
    for treatment in ('stock', 'patched'):
        lab_root = root / (treatment + '-lab')
        output = root / treatment
        state = lab.up(argparse.Namespace(root=lab_root, fixtures=fixtures, engine=args.engine,
            connection=args.connection, port=args.port, pull=False,
            patch=root / 'patch' if treatment == 'patched' else None))
        try:
            versions[treatment] = json.loads((lab_root / 'version.json').read_text())
            common = ['--url', state['url'], '--password-file', lab_root / 'admin-password',
                      '--fixtures', fixtures, '--output', output]
            command(logs / (treatment + '-publish.log'), 'affine_fix.validate', 'publish', *common)
            for gutter in (0, 1):
                label = f'{treatment}-g{gutter}'
                print('Scanning', label, '(quick)' if args.quick else '(full matrix)', flush=True)
                command(logs / (label + '-configure.log'), 'affine_fix.validate', 'configure',
                        *common, '--gutter', gutter)
                command(logs / (label + '-scan.log'), 'affine_fix.validate', 'scan',
                        *common, '--gutter', gutter, '--label', label, *(['--quick'] if args.quick else []))
                summaries[label] = json.loads((output / 'summary' / (label + '.json')).read_text())
            if treatment == 'patched':
                command(logs / 'regression.log', 'affine_fix.validate', 'regression', *common, '--gutter', 1)
                command(logs / 'cache.log', 'affine_fix.validate', 'cache-check', *common, '--label', 'patched-g1')
        finally:
            lab.stop(state, lab_root)
    probe.FIXTURE_ROOT = None
    entries = probe.verify(fixtures)
    if before != {e['name']: e['sha256'] for e in entries}:
        raise RuntimeError('Source fixtures changed during reproduction')
    expected_count = sum(len(list(probe.cases(e, args.quick))) for e in entries)
    for label, summary in summaries.items():
        for route, result in summary['routes'].items():
            if result['successful_requests'] + result['errors'] != expected_count:
                raise RuntimeError(f'Incomplete scan: {label} {route}')
            if route == 'gwc' and result['cache_headers'] != {'MISS': result['successful_requests']}:
                raise RuntimeError(f'Unexpected cached responses: {label}')
    failures = []
    for route, result in summaries['patched-g1']['routes'].items():
        if result['errors'] or result['interior_missing_pixels'] or result['north_up_missing_pixels']:
            failures.append(route + ': rendering regression')
    report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'lock': lab.load_lock(),
              'quick': args.quick, 'requests_per_treatment_and_route': expected_count,
              'fixtures_unchanged': True, 'fixture_sha256': before, 'versions': versions,
              'build': json.loads((root / 'patch/build.json').read_text()),
              'regression': json.loads((root / 'patched/regression-result.json').read_text()),
              'cache': json.loads((root / 'patched/summary/patched-g1-cache.json').read_text()),
              'treatments': {label: value['routes'] for label, value in summaries.items()},
              'servers_stopped': True, 'passed': not failures, 'failures': failures}
    probe.write_json(root / 'result.json', report)
    print(json.dumps(report['treatments'], indent=2), flush=True)
    print('Results:', root / 'result.json', flush=True)
    if failures:
        raise AssertionError('; '.join(failures))


if __name__ == '__main__':
    main()
