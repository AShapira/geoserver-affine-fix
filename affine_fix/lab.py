"""Create an isolated official GeoServer lab with its own catalog and copied fixtures."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import secrets
import subprocess
import tarfile
import time
import uuid

import requests

from . import probe

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'org.geoserver-affine-fix.lab'
SERVER_FIXTURES = '/opt/affine-fixtures'


def call(engine, *args, data=None, check=True):
    result = subprocess.run([*engine, *args], input=data, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result


def archive(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tar:
        for name, path in files.items():
            tar.add(path, arcname=name, recursive=False)
    return buf.getvalue()


def owned_container(state):
    result = call(state['engine'], 'inspect', state['container_id'])
    info = json.loads(result.stdout)[0]
    if info.get('Config', {}).get('Labels', {}).get(LABEL) != state['owner']:
        raise RuntimeError('Refusing to manage a container without this lab ownership label')
    return info


def stop(state, root):
    owned_container(state)
    # Logs may contain image startup details: retain locally, never publish them.
    logs = call(state['engine'], 'logs', state['container_id'], check=False)
    (root / 'server.log').write_bytes(logs.stdout + logs.stderr)
    call(state['engine'], 'stop', '--time', '20', state['container_id'])


def load_lock():
    return json.loads((ROOT / 'runtime/lock.json').read_text())


def image_mounts(config):
    paths = set(config.get('Config', {}).get('Volumes') or {})
    paths.add('/opt/geoserver_data')
    return [arg for path in sorted(paths) for arg in ('--tmpfs', path)]


def patch_payload(directory, lock):
    manifest = json.loads((directory / 'build.json').read_text())
    if manifest['image'] != lock['image'] or set(manifest['libraries']) != set(lock['libraries']):
        raise RuntimeError('Patch was not built for the pinned official image')
    files = {}
    for jar, spec in lock['libraries'].items():
        details = manifest['libraries'][jar]
        if details['original_sha256'] != spec['sha256'] or details['changed_entries'] != [spec['class']]:
            raise RuntimeError('Patch targets an unexpected library or class: ' + jar)
        payload = directory / jar
        if hashlib.sha256(payload.read_bytes()).hexdigest() != details['patched_sha256']:
            raise RuntimeError('Patch payload checksum mismatch: ' + jar)
        files[jar] = payload
    return files


def install_patch(engine, container, directory, lock):
    files = patch_payload(directory, lock)
    lib = lock['library_directory']
    for jar, spec in lock['libraries'].items():
        data = call(engine, 'cp', container + ':' + lib + '/' + jar, '-').stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            if len(members) != 1 or hashlib.sha256(tar.extractfile(members[0]).read()).hexdigest() != spec['sha256']:
                raise RuntimeError('Refusing to replace a different original JAR: ' + jar)
    call(engine, 'cp', '-', container + ':' + lib, data=archive(files))


def up(args):
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    state_file = root / 'lab.json'
    if state_file.exists():
        raise RuntimeError('This lab already exists; use a different --root')
    probe.FIXTURE_ROOT = None
    entries = probe.verify(args.fixtures)
    if len(entries) != 14 or any(e['size'] != 4096 for e in entries):
        raise RuntimeError('Generate the full 4096-pixel fixtures before starting a lab')
    engine = [args.engine] + (['--connection', args.connection] if args.connection else [])
    lock = load_lock()
    selected_image = lock['image']
    if args.patch:
        patch_payload(args.patch, lock)
    if args.pull:
        call(engine, 'pull', selected_image)
    config = json.loads(call(engine, 'image', 'inspect', selected_image).stdout)[0]
    mounts = image_mounts(config)
    owner = uuid.uuid4().hex
    name = 'geoserver-affine-lab-' + owner[:12]
    password = secrets.token_hex(24)
    password_file = root / 'admin-password'
    password_file.write_text(password + '\n')
    password_file.chmod(0o600)
    env = root / 'server.env'
    env.write_text('GEOSERVER_ADMIN_USER=admin\nGEOSERVER_ADMIN_PASSWORD=' + password
                   + '\nSKIP_DEMO_DATA=true\nINSTALL_EXTENSIONS=false\nEXTRA_JAVA_OPTS=-Xms512m -Xmx2g\n')
    env.chmod(0o600)
    command = ['create', '--pull=never', '--name', name, '--label', LABEL + '=' + owner,
               '--cpus', '2', '--memory', '6g', '-p', f'127.0.0.1:{args.port}:8080',
               '--env-file', str(env), *mounts]
    command += [selected_image]
    container_id = call(engine, *command).stdout.decode().strip()
    state = {'owner': owner, 'container_id': container_id, 'container_name': name,
             'engine': engine, 'image': selected_image, 'image_id': config['Id'],
             'url': f'http://127.0.0.1:{args.port}/geoserver',
             'fixtures': str(args.fixtures.resolve()), 'server_fixture_dir': SERVER_FIXTURES,
             'password_file': str(password_file), 'patch': str(args.patch.resolve()) if args.patch else None}
    probe.write_json(state_file, state)
    state_file.chmod(0o600)
    try:
        files = {'affine-fixtures/' + Path(e['path']).name: Path(e['path']) for e in entries}
        if args.patch:
            install_patch(engine, container_id, args.patch, lock)
        call(engine, 'cp', '-', container_id + ':/opt', data=archive(files))
        call(engine, 'start', container_id)
        session = requests.Session()
        session.auth = ('admin', password)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                response = session.get(state['url'] + '/rest/about/version.json', timeout=5)
                if response.ok:
                    version = response.json()
                    installed = {r['@name']: str(r['Version']) for r in version['about']['resource']}
                    for component, expected in [('GeoServer', lock['geoserver']), ('GeoTools', lock['geotools']),
                                                 ('GeoWebCache', lock['geowebcache'])]:
                        if installed.get(component) != expected:
                            raise RuntimeError('Unexpected running ' + component + ' version')
                    probe.write_json(root / 'version.json', version)
                    print('Ready:', state['url'], flush=True)
                    print('Lab state:', state_file, flush=True)
                    return state
            except requests.RequestException:
                pass
            info = owned_container(state)
            if info['State']['Status'] == 'exited':
                raise RuntimeError('Lab exited before readiness; see private server.log')
            time.sleep(2)
        raise RuntimeError('Lab readiness timed out; see private server.log')
    except BaseException:
        stop(state, root)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'status', 'stop', 'down'])
    parser.add_argument('--root', type=Path, default=Path('.runs/lab'))
    parser.add_argument('--fixtures', type=Path, default=Path('.runs/fixtures'))
    parser.add_argument('--engine', default='podman')
    parser.add_argument('--connection')
    parser.add_argument('--port', type=int, default=18096)
    parser.add_argument('--pull', action='store_true', help='Fetch the selected image before creation')
    parser.add_argument('--patch', type=Path, help='Output directory from affine-build')
    args = parser.parse_args()
    if args.port < 1024 or args.port > 65535:
        parser.error('--port must be between 1024 and 65535')
    if args.action == 'up':
        up(args)
        return
    state_file = args.root / 'lab.json'
    state = json.loads(state_file.read_text())
    info = owned_container(state)
    if args.action == 'status':
        print(json.dumps({'name': state['container_name'], 'state': info['State']['Status'],
                          'url': state['url']}, indent=2))
    else:
        stop(state, args.root)
        if args.action == 'down':
            owned_container(state)
            call(state['engine'], 'rm', state['container_id'])
            state_file.rename(args.root / ('removed-' + state['owner'] + '.json'))
            print('Removed only this lab container; local evidence retained')


if __name__ == '__main__':
    main()
