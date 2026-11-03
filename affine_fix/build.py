"""Compile the two source corrections against the pinned official GeoServer image."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import uuid
import zipfile

from .lab import archive, call, image_mounts, load_lock, ROOT
from .probe import write_json


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_class(original, entry, compiled):
    """Preserve every other entry, metadata and archive comment verbatim."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, 'w') as target:
        if entry not in source.namelist():
            raise RuntimeError('Missing original class: ' + entry)
        target.comment = source.comment
        for info in source.infolist():
            target.writestr(info, compiled if info.filename == entry else source.read(info.filename))
    result = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(original)) as a, zipfile.ZipFile(io.BytesIO(result)) as b:
        changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
        if a.namelist() != b.namelist() or changed != [entry]:
            raise RuntimeError('Unexpected archive changes: ' + repr(changed))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='podman')
    parser.add_argument('--connection')
    parser.add_argument('--pull', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('.artifacts/patch'))
    args = parser.parse_args()
    lock = load_lock()
    for name, sha in lock['source_sha256'].items():
        if digest((ROOT / name).read_bytes()) != sha:
            raise RuntimeError('Source checksum mismatch: ' + name)
    engine = [args.engine] + (['--connection', args.connection] if args.connection else [])
    if args.pull:
        call(engine, 'pull', lock['image'])
    config = json.loads(call(engine, 'image', 'inspect', lock['image']).stdout)[0]
    name = 'geoserver-affine-compile-' + uuid.uuid4().hex[:12]
    container = call(engine, 'run', '-d', '--pull=never', '--name', name,
                     '--label', 'org.geoserver-affine-fix.build=true',
                     '--network', 'none', '--cpus', '2', '--memory', '2g',
                     *image_mounts(config), '--entrypoint', 'sleep', lock['image'], 'infinity').stdout.decode().strip()
    try:
        lib = lock['library_directory']
        originals = {}
        for jar, spec in lock['libraries'].items():
            data = call(engine, 'exec', container, 'cat', lib + '/' + jar).stdout
            if digest(data) != spec['sha256']:
                raise RuntimeError('Image library checksum mismatch: ' + jar)
            originals[jar] = data
        files = {Path(spec['source']).name: ROOT / spec['source'] for spec in lock['libraries'].values()}
        files['AffineScanlineRegression.java'] = ROOT / 'tests/java/AffineScanlineRegression.java'
        call(engine, 'exec', container, 'mkdir', '-p', '/tmp/affine-build/classes', '/tmp/affine-build/tests')
        call(engine, 'exec', '-i', container, 'tar', '-xf', '-', '-C', '/tmp/affine-build', data=archive(files))
        call(engine, 'exec', container, 'javac', '--release', str(lock['java_release']), '-proc:none',
             '-cp', lib + '/*', '-d', '/tmp/affine-build/classes',
             *['/tmp/affine-build/' + Path(spec['source']).name for spec in lock['libraries'].values()])
        call(engine, 'exec', container, 'javac', '--release', str(lock['java_release']), '-proc:none',
             '-cp', lib + '/*', '-d', '/tmp/affine-build/tests', '/tmp/affine-build/AffineScanlineRegression.java')
        test = 'org.eclipse.imagen.media.affine.AffineScanlineRegression'
        baseline = call(engine, 'exec', container, 'java', '-cp', '/tmp/affine-build/tests:' + lib + '/*', test, check=False)
        if baseline.returncode == 0 or b'Expected [0,2) but got RangeInt[0, 3]' not in baseline.stderr:
            raise RuntimeError('Official library did not fail the expected regression')
        corrected = call(engine, 'exec', container, 'java', '-cp',
                         '/tmp/affine-build/tests:/tmp/affine-build/classes:' + lib + '/*', test)
        data = call(engine, 'exec', container, 'tar', '-cf', '-', '-C', '/tmp/affine-build/classes', '.').stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            classes = {m.name.removeprefix('./'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
        if set(classes) != {spec['class'] for spec in lock['libraries'].values()}:
            raise RuntimeError('Unexpected compiler output: ' + repr(list(classes)))
        args.output.mkdir(parents=True, exist_ok=True)
        results = {}
        for jar, spec in lock['libraries'].items():
            data = replace_class(originals[jar], spec['class'], classes[spec['class']])
            (args.output / jar).write_bytes(data)
            results[jar] = {'original_sha256': digest(originals[jar]), 'patched_sha256': digest(data),
                            'changed_entries': [spec['class']], 'bytes': len(data)}
        write_json(args.output / 'build.json', {
            'image': lock['image'], 'geoserver': lock['geoserver'], 'custom_image_built': False,
            'java': call(engine, 'exec', container, 'javac', '-version').stdout.decode().strip(),
            'libraries': results, 'original_regression_exit': baseline.returncode,
            'patched_regression_exit': corrected.returncode,
        })
        (args.output / 'regression-original.txt').write_bytes(baseline.stdout + baseline.stderr)
        (args.output / 'regression-patched.txt').write_bytes(corrected.stdout + corrected.stderr)
        print(json.dumps(results, indent=2))
        print(corrected.stdout.decode().strip())
    finally:
        # Only this unique compiler container; all declared volumes use tmpfs.
        call(engine, 'rm', '-f', container)


if __name__ == '__main__':
    main()
