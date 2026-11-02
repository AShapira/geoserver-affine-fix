#!/usr/bin/env python3
"""Package public deployment files; never include private lab artifacts."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'kartoza-geoserver-2.28.5-affine-fix.zip'


def public_files():
    names = json.loads((ROOT / 'package-files.json').read_text())
    for name in names:
        path = ROOT / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            raise RuntimeError('Invalid public package path: ' + name)
        if not path.is_file():
            raise RuntimeError('Build required; missing package input: ' + name)
        yield path


def main():
    files = list(public_files())
    for line in (ROOT / 'jars.sha256.tsv').read_text().splitlines():
        name, _, checksum = line.split('\t')
        if hashlib.sha256((ROOT / 'jars' / name).read_bytes()).hexdigest() != checksum:
            raise RuntimeError('Payload checksum mismatch: ' + name)
    checksums = ROOT / 'SHA256SUMS'
    checksums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in files))
    files.append(checksums)
    with zipfile.ZipFile(ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname='kartoza-geoserver-affine-fix/' + path.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix('.zip.sha256').write_text(digest + '  ' + ARCHIVE.name + '\n')
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert not any('/.artifacts/' in n or 'admin-password' in n for n in archive.namelist())
    print(f'{ARCHIVE.name}: {len(files)} files, {ARCHIVE.stat().st_size:,} bytes\nSHA-256 {digest}')


if __name__ == '__main__':
    main()
