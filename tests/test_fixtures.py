import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio

from affine_fix import probe
from affine_fix.lab import owned_container


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name) / 'fixtures'
        with contextlib.redirect_stdout(io.StringIO()):
            probe.fixtures(cls.root, size=32)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_affine_metadata_pixels_and_nearest_overviews(self):
        entries = probe.verify(self.root)
        self.assertEqual(len(entries), 14)
        for item in entries:
            with self.subTest(name=item['name']), rasterio.open(item['path']) as dataset:
                self.assertEqual(dataset.crs.to_epsg(), 3857)
                np.testing.assert_allclose(dataset.transform.to_gdal(), item['gt'])
                np.testing.assert_array_equal(dataset.read(1), probe.pattern(32))
                self.assertEqual(dataset.overviews(1), [2, 4, 8, 16] if item['overviews'] else [])
                if item['overviews']:
                    np.testing.assert_array_equal(dataset.read(1, out_shape=(16, 16)), probe.pattern(32)[::2, ::2])

    def test_manifest_survives_directory_move(self):
        with tempfile.TemporaryDirectory() as folder:
            relocated = Path(folder) / 'relocated'
            shutil.copytree(self.root, relocated)
            entries = probe.verify(relocated)
            self.assertTrue(all(Path(item['path']).is_relative_to(relocated) for item in entries))
            self.assertTrue(all(not Path(item['path']).is_absolute()
                                for item in json.loads((relocated / 'fixtures.json').read_text())))

    def test_prepare_preserves_existing_files(self):
        before = (self.root / 'fixtures.json').read_bytes()
        probe.fixtures(self.root, size=32)
        self.assertEqual(before, (self.root / 'fixtures.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'different size'):
            probe.fixtures(self.root, size=64)

    def test_corrupt_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / 'corrupt'
            shutil.copytree(self.root, copied)
            path = copied / 'fixtures/rot30_base.tif'
            path.chmod(0o644)
            path.write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError, 'Fixture changed: rot30_base'):
                probe.verify(copied)

    def test_original_container_paths_can_be_relocated(self):
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / 'old-manifest'
            shutil.copytree(self.root, copied)
            entries = json.loads((copied / 'fixtures.json').read_text())
            for item in entries:
                item['path'] = '/old/container/fixtures/' + item['name'] + '.tif'
            (copied / 'fixtures.json').write_text(json.dumps(entries))
            self.assertEqual(len(probe.verify(copied)), 14)


class LabOwnershipTests(unittest.TestCase):
    def test_refuses_unowned_container_before_any_stop(self):
        state = {'engine': ['podman'], 'container_id': 'test', 'owner': 'ours'}
        with patch('affine_fix.lab.call') as call:
            call.return_value.stdout = b'[{"Config":{"Labels":{}}}]'
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                owned_container(state)
            call.assert_called_once_with(['podman'], 'inspect', 'test')


if __name__ == '__main__':
    unittest.main()
