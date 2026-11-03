import unittest
from affine_fix.mask_report import case_timings, quality_verdict


class MaskReportTests(unittest.TestCase):
    def test_failed_or_mismatched_images_cannot_disappear_from_verdict(self):
        rows = [{'error': 'invalid_image_response'}, {'missing': 1, 'alpha_mismatch': 1},
                {'spurious': 2, 'color_mismatch': 3}, {}]
        self.assertEqual(quality_verdict(rows), dict(checks=4, errors=1, missing=1,
                         spurious=2, alpha_mismatch=1, color_mismatch=3))

    def test_fresh_jvms_have_equal_weight(self):
        blocks = []
        for replicate, repeats, before, after in [(0, 5, 10, 5), (1, 1, 30, 24)]:
            for _ in range(repeats):
                for variant, value in [('stock', before), ('both', after)]:
                    blocks.append(dict(profile='wms', concurrency=1, replicate=replicate,
                        variant=variant, summary={'by_fixture': {'rgb_r30_base': {'median_ms': value}}}))
        result = case_timings(blocks, 'rgb', 30)
        self.assertEqual(result['baseline_ms'], 20)
        self.assertEqual(result['optimized_ms'], 14.5)
        self.assertAlmostEqual(result['median_reduction_percent'], 35)


if __name__ == '__main__':
    unittest.main()
