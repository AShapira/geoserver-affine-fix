#!/usr/bin/env python3
"""Check a compiled compatibility candidate in a new isolated lab."""
import argparse
from collections import Counter
import json
from pathlib import Path
import uuid

from affine_fix import lab, probe
from inspect_versions import ROOT, WORK


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    parser.add_argument('--phase', choices=['stock', 'patched'], required=True)
    parser.add_argument('--engine', default='podman')
    parser.add_argument('--connection')
    parser.add_argument('--fixtures', type=Path, default=Path('.runs/fixtures'))
    parser.add_argument('--port', type=int, default=18097)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    version_root = WORK / args.tag.replace('--', '-')
    info = json.loads((version_root / 'inspection.json').read_text())
    output = version_root / ('render-' + args.phase + '-' + uuid.uuid4().hex[:8])
    state = lab.up(argparse.Namespace(root=output / 'lab', fixtures=args.fixtures,
        engine=args.engine, connection=args.connection, image=info['image'],
        port=args.port, pull=False,
        bundle=version_root / 'candidate' if args.phase == 'patched' else None))
    probe.BASE = state['url']
    probe.FIXTURE_ROOT = args.fixtures.resolve()
    probe.SERVER_FIXTURE_DIR = state['server_fixture_dir']
    session = probe.session('admin', state['password_file'])
    entries = probe.verify(output)
    result = {'tag': args.tag, 'phase': args.phase, 'image': info['image'],
              'container': state['container_name'], 'full_matrix': args.full,
              'source_fixture_sha256': {e['name']: e['sha256'] for e in entries},
              'version': json.loads((output / 'lab/version.json').read_text())}
    try:
        probe.snapshot(output, session)
        probe.publish(output, session)
        result['active_jars'] = {}
        import hashlib
        for name in info['original_jars']:
            payload = lab.call(state['engine'], 'exec', state['container_id'], 'cat',
                '/usr/local/tomcat/webapps/geoserver/WEB-INF/lib/' + name).stdout
            actual = hashlib.sha256(payload).hexdigest()
            wanted = info['original_jars'][name] if args.phase == 'stock' else info['patched_jars'][name]['sha256']
            assert actual == wanted, name
            result['active_jars'][name] = actual
        # This catalog exists only in the newly created lab's tmpfs.
        control = '/opt/geoserver/data_dir/controlflow.properties'
        current = lab.call(state['engine'], 'exec', state['container_id'], 'cat', control, check=False)
        if current.returncode == 0:
            filtered = b'\n'.join(line for line in current.stdout.splitlines()
                if not line.strip().startswith(b'user.ows.wms.getmap=')) + b'\n'
            lab.call(state['engine'], 'exec', '-i', state['container_id'], 'tee', control, data=filtered)
            result['isolated_wms_rate_rule_removed'] = filtered != current.stdout
            import time
            time.sleep(3)
        selected = [('rot30_base', (24, 10021196, 6798186))]
        if args.phase == 'patched':
            selected.append(('rotm30_base', (20, 626306, 424906)))
        samples = []
        for name, tile in selected:
            item = next(e for e in entries if e['name'] == name)
            for route in ('wms', 'gwc'):
                response = probe.request_image(session, item, tile, route=route)
                probe.record(output, args.phase + '-g0-samples', *response)
                samples.append(response[0])
                if name == 'rot30_base':
                    assert response[0]['missing_pixels'] == 0 if args.phase == 'patched' else response[0]['missing_pixels'] > 1000
        result['patched_g0_samples' if args.phase == 'patched' else 'minimal'] = samples
        gutter = 1 if args.phase == 'patched' else 0
        probe.configure(output, session, gutter, 1)
        result['gutter'] = gutter
        if args.phase == 'patched':
            probe.regression(output, session, 1)
            result['regression'] = json.loads((output / 'regression-result.json').read_text())
            if args.full:
                probe.configure(output, session, 1, 1)
                probe.scan(output, session, label='patched-g1',
                    routes=[('wms', 'nearest neighbor'), ('gwc', 'nearest neighbor')], pad=1)
                rows = [json.loads(line) for line in (output / 'patched-g1.jsonl').read_text().splitlines()]
                error_file = output / 'patched-g1-errors.jsonl'
                errors = [json.loads(line) for line in error_file.read_text().splitlines()] if error_file.exists() else []
                result['matrix'] = {}
                for route in ('wms', 'gwc'):
                    subset = [r for r in rows if r['route'] == route]
                    interior = [r for r in subset if r['valid_pixels'] == 65536]
                    result['matrix'][route] = {
                        'successful_requests': len(subset), 'errors': sum(r['route'] == route for r in errors),
                        'missing_pixels': sum(r['missing_pixels'] for r in subset),
                        'interior_requests': len(interior),
                        'interior_missing_pixels': sum(r['missing_pixels'] for r in interior),
                        'north_up_missing_pixels': sum(r['missing_pixels'] for r in subset if r['name'].startswith('rot0_')),
                        'cache_headers': dict(Counter(r['cache'] for r in subset))}
            item = next(e for e in entries if e['name'] == 'rot30_base')
            probe.truncate(session, item['name'])
            result['cache_sequence'] = [probe.request_image(session, item, (24, 10021196, 6798186), route='gwc')[0]['cache'] for _ in range(2)]
            assert result['cache_sequence'] == ['MISS', 'HIT']
        result['fixtures_unchanged'] = bool(probe.verify(output))
    finally:
        lab.stop(state, output / 'lab')
        result['container_state_after'] = lab.owned_container(state)['State']['Status']
        probe.write_json(output / 'result.json', result)
        print('Saved', output, flush=True)


if __name__ == '__main__':
    main()
