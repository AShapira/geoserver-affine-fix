import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from affine_fix.documentation_figures import composite, image_path, publish


class DocumentationEvidenceTests(unittest.TestCase):
    def capture(self, root, changed=False):
        (root/'capture.json').write_text('{}')
        expected=np.full((16,16,4),255,dtype=np.uint8)
        expected[...,:3]=[40,80,160]
        rows=[]
        for variant in ('baseline','current'):
            actual=expected.copy()
            actual[2 if changed and variant=='current' else 1,1,3]=0
            row=dict(name='rgba_r30_base',tile=[15,1,1],gutter=1,variant=variant,
                     missing=1,spurious=0,alpha_mismatch=1,color_mismatch=0)
            for is_expected,array in ((False,actual),(True,expected)):
                path=image_path(root,variant,row,is_expected);path.parent.mkdir(parents=True,exist_ok=True)
                Image.fromarray(array).save(path)
            rows.append(row)
        (root/'checks.json').write_text(json.dumps(rows))

    def test_same_error_count_at_a_different_pixel_is_a_new_regression(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.capture(root,changed=True)
            with self.assertRaisesRegex(ValueError,'New difference'):
                publish(root,root)

    def test_unchanged_failure_remains_visible_in_public_evidence(self):
        with tempfile.TemporaryDirectory() as folder, patch('affine_fix.documentation_figures.figure',return_value={}):
            root=Path(folder);self.capture(root)
            publish(root,root)
            report=json.loads((root/'raster-comparisons.json').read_text())
            self.assertEqual(len(report['known_downsampling_mismatches']),1)
            self.assertEqual(report['known_downsampling_mismatches'][0]['missing'],1)
            self.assertTrue(report['known_downsampling_mismatches'][0]['identical_to_previous_candidate'])
            self.assertEqual(report['checks'][1]['alpha_mismatch'],1)

    def test_checkerboard_uses_alpha_without_mutating_source(self):
        source=np.array([[[0,100,200,0],[0,100,200,128],[0,100,200,255]]],dtype=np.uint8)
        original=source.copy();result=composite(source)
        np.testing.assert_array_equal(result[0],[[235,235,235],[117,167,217],[0,100,200]])
        np.testing.assert_array_equal(source,original)


if __name__=='__main__':unittest.main()
