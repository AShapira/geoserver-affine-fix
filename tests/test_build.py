import hashlib
import difflib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from affine_fix.build import replace_class
from affine_fix.lab import patch_payload, load_lock, ROOT


class BuildTests(unittest.TestCase):
    def test_locked_sources_and_reviewable_diffs_match(self):
        lock = load_lock()
        for name, digest in lock['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)
        upstream_paths = {
            'geotools': 'modules/library/render/src/main/java/org/geotools/renderer/lite/gridcoverage2d/GridCoverageReaderHelper.java',
            'imagen': 'modules/affine/src/main/java/org/eclipse/imagen/media/affine/AffineOpImage.java',
        }
        for project, target in upstream_paths.items():
            source = ROOT / 'source' / project / Path(target).name
            original = Path(str(source) + '.original')
            expected = ''.join(difflib.unified_diff(original.read_text().splitlines(True),
                source.read_text().splitlines(True), fromfile='a/' + target, tofile='b/' + target))
            self.assertEqual((ROOT / 'patches' / (project + '.patch')).read_text(), expected)

    def test_additional_candidate_diffs_match_locked_sources(self):
        for patch in (ROOT / 'patches').glob('imagen-*.patch'):
            text = patch.read_text()
            target = text.splitlines()[0].removeprefix('--- a/')
            source = ROOT / 'source/imagen' / Path(target).name
            original = Path(str(source) + '.original')
            expected = ''.join(difflib.unified_diff(original.read_text().splitlines(True),
                source.read_text().splitlines(True), fromfile='a/' + target, tofile='b/' + target))
            self.assertEqual(text, expected)

    def test_replacement_preserves_other_entries_metadata_and_comment(self):
        source = io.BytesIO()
        with zipfile.ZipFile(source, 'w') as archive:
            archive.comment = b'upstream archive'
            archive.writestr('package/Example.class', b'original class')
            info = zipfile.ZipInfo('META-INF/NOTICE', (2026, 1, 2, 3, 4, 6))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, b'upstream notice')
        result = replace_class(source.getvalue(), 'package/Example.class', b'fixed class')
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            self.assertEqual(archive.read('package/Example.class'), b'fixed class')
            self.assertEqual(archive.read('META-INF/NOTICE'), b'upstream notice')
            self.assertEqual(archive.getinfo('META-INF/NOTICE').date_time, info.date_time)
            self.assertEqual(archive.getinfo('META-INF/NOTICE').external_attr, info.external_attr)
            self.assertEqual(archive.comment, b'upstream archive')
        with self.assertRaisesRegex(RuntimeError, 'Missing original class'):
            replace_class(source.getvalue(), 'Missing.class', b'fixed class')

    def test_payload_rejects_other_image_and_corrupt_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b'patched library'
            (root / 'test.jar').write_bytes(payload)
            spec = {'sha256': 'original', 'class': 'Test.class'}
            lock = {'image': 'official@sha256:123', 'libraries': {'test.jar': spec}}
            manifest = {'image': lock['image'], 'libraries': {'test.jar': {
                'original_sha256': 'original', 'patched_sha256': hashlib.sha256(payload).hexdigest(),
                'changed_entries': ['Test.class']}}}
            (root / 'build.json').write_text(json.dumps(manifest))
            self.assertEqual(patch_payload(root, lock), {'test.jar': root / 'test.jar'})
            with self.assertRaisesRegex(RuntimeError, 'pinned official image'):
                patch_payload(root, dict(lock, image='other'))
            (root / 'test.jar').write_bytes(b'corrupted')
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                patch_payload(root, lock)


if __name__ == '__main__':
    unittest.main()
