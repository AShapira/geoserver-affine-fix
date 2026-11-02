#!/usr/bin/env python3
"""Validate immutable fixtures against an explicitly selected isolated GeoServer."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import requests

from . import probe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['ready', 'publish', 'scan', 'regression', 'configure', 'cache-check'])
    parser.add_argument('--url', default='http://127.0.0.1:18096/geoserver')
    parser.add_argument('--password-file', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, default=Path('.runs/fixtures'))
    parser.add_argument('--label', default='stock-g0')
    parser.add_argument('--gutter', type=int, default=0)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('.runs/rendering'))
    parser.add_argument('--username', default='admin')
    parser.add_argument('--server-fixture-dir', default='/opt/affine-fixtures')
    args = parser.parse_args(argv)
    if args.gutter < 0:
        parser.error('--gutter must be nonnegative')
    if not args.label or Path(args.label).name != args.label or args.label in ('.', '..'):
        parser.error('--label must be a simple name')
    probe.BASE = args.url
    output = args.output.resolve()
    evidence = output / 'summary'
    evidence.mkdir(exist_ok=True, parents=True)
    probe.FIXTURE_ROOT = args.fixtures.resolve()
    probe.SERVER_FIXTURE_DIR = args.server_fixture_dir
    output.mkdir(exist_ok=True, parents=True)
    session = requests.Session()
    session.auth = (args.username, args.password_file.read_text().strip())

    if args.action == 'ready':
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                r = session.get(args.url + '/rest/about/version.json', timeout=5)
                if r.ok:
                    (evidence / (args.label + '-version.json')).write_text(json.dumps(r.json(), indent=2) + '\n')
                    print('GeoServer ready:', args.url, flush=True)
                    return
            except requests.RequestException:
                pass
            time.sleep(2)
        raise RuntimeError('GeoServer readiness timed out')

    entries = probe.verify(output)
    if any(e['size'] != 4096 for e in entries):
        parser.error('Rendering validation requires full 4096-pixel fixtures')
    if args.action == 'publish':
        probe.snapshot(output, session)
        probe.publish(output, session)
    elif args.action == 'configure':
        probe.configure(output, session, args.gutter, 1)
    elif args.action == 'scan':
        probe.scan(output, session, quick=args.quick, label=args.label,
                   routes=[('wms', 'nearest neighbor'), ('gwc', 'nearest neighbor')], pad=args.gutter)
        rowfile = output / (args.label + '.jsonl')
        rows = [json.loads(line) for line in rowfile.read_text().splitlines()] if rowfile.exists() else []
        errorfile = output / (args.label + '-errors.jsonl')
        errors = [json.loads(line) for line in errorfile.read_text().splitlines()] if errorfile.exists() else []
        summary = {'label': args.label, 'gutter': args.gutter, 'fixture_sha256': {e['name']: e['sha256'] for e in entries}, 'routes': {}}
        for route in ('wms', 'gwc'):
            subset = [r for r in rows if r['route'] == route]
            interior = [r for r in subset if r['valid_pixels'] == 65536]
            summary['routes'][route] = {
                'successful_requests': len(subset), 'errors': len([r for r in errors if r['route'] == route]),
                'missing_pixels': sum(r['missing_pixels'] for r in subset),
                'interior_requests': len(interior), 'interior_missing_pixels': sum(r['missing_pixels'] for r in interior),
                'north_up_missing_pixels': sum(r['missing_pixels'] for r in subset if r['name'].startswith('rot0_')),
                'cache_headers': dict(Counter(r['cache'] for r in subset)),
            }
        (evidence / (args.label + '.json')).write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary['routes'], indent=2), flush=True)
    elif args.action == 'regression':
        probe.regression(output, session, args.gutter)
    elif args.action == 'cache-check':
        item = next(e for e in entries if e['name'] == 'rot30_base')
        probe.truncate(session, item['name'])
        tile = (24, 10021196, 6798186)
        first = probe.request_image(session, item, tile, route='gwc')[0]
        second = probe.request_image(session, item, tile, route='gwc')[0]
        assert first['cache'] == 'MISS' and second['cache'] == 'HIT', (first, second)
        (evidence / (args.label + '-cache.json')).write_text(json.dumps([first, second], indent=2) + '\n')
        print('Verified GWC MISS followed by HIT', flush=True)
    probe.verify(output)


if __name__ == '__main__':
    main()
