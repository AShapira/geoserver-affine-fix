import io
import json
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from affine_fix import benchmark, benchmark_metrics as bm, benchmark_workloads as bw, lab, probe
from affine_fix.performance_report import aggregate, paired_change, jfr_events


def entries():
    result = []
    for angle, shear in [(0, False), (15, False), (30, False), (45, False), (75, False), (-30, False), (30, True)]:
        for overview in (False, True):
            name = ('shear' if shear else 'rot' + str(angle).replace('-', 'm')) + ('_ovr' if overview else '_base')
            result.append(dict(name=name, size=4096, gt=probe.affine(angle, shear=shear)))
    for name, angle in [('large_rot0_base', 0), ('large_rot30_base', 30), ('large_rot30_ovr', 30)]:
        result.append(dict(name=name, size=16384, gt=probe.affine(angle, size=16384)))
    return result


class WorkloadTests(unittest.TestCase):
    def test_blockwise_large_pattern_matches_original_generator(self):
        size = 128
        source = probe.pattern(size)
        for y in range(0, size, 16):
            for x in range(0, size, 16):
                np.testing.assert_array_equal(source[y:y + 16, x:x + 16],
                    bw.pixels(size, np.arange(x, x + 16)[None, :], np.arange(y, y + 16)[:, None]))

    def test_large_pattern_preserves_uint32_overflow(self):
        x, y = 16383, 16382
        expected = 32 + (((x * 73856093) % 2**32 ^ (10000 * 19349663) % 2**32) % 192)
        self.assertEqual(int(bw.pixels(16384, x, 10000)), expected)
        self.assertEqual(int(bw.pixels(16384, x, y)), 208)

    def test_workloads_are_unique_interior_and_cover_all_scales(self):
        items = entries()
        workloads = bw.workloads(items)
        self.assertEqual({k: len(v) for k, v in workloads.items()},
                         {'core': 256, 'large': 192, 'geometry': 224, 'control': 64})
        lookup = {e['name']: e for e in items}
        for jobs in workloads.values():
            self.assertEqual(len(jobs), len({(j['name'], *j['tile']) for j in jobs}))
            self.assertTrue(all(bw.interior(lookup[j['name']], j['tile']) for j in jobs))
        self.assertEqual({j['tile'][0] for j in workloads['large']}, {14, 16, 18, 20, 22})

    def test_formula_oracle_matches_source_pixel_oracle(self):
        item = dict(size=128, gt=probe.affine(30, size=128), name='example')
        tile = probe.tile_at(24, *probe.world(item['gt'], 64, 80))
        actual, valid = bw.reference(item, tile)
        expected, expected_valid = probe.expected(probe.pattern(128), item['gt'], probe.tile(*tile))
        np.testing.assert_array_equal(valid, expected_valid)
        np.testing.assert_array_equal(actual[valid], expected[valid])

    def test_ablation_and_fixture_guards(self):
        lock = lab.load_lock()
        for component, prefix in [('geotools', 'org/geotools/'), ('imagen', 'org/eclipse/imagen/')]:
            selected = lab.selected_libraries(lock, component)
            self.assertEqual(len(selected), 1)
            self.assertTrue(next(iter(selected.values()))['class'].startswith(prefix))
        with self.assertRaises(ValueError):
            lab.selected_libraries(lock, 'unvalidated')
        lab.validate_fixture_set(entries(), 'benchmark')
        lab.validate_fixture_set(entries()[:14])
        with self.assertRaises(RuntimeError):
            lab.validate_fixture_set(entries())
        with self.assertRaises(RuntimeError):
            lab.validate_fixture_set(entries() + [entries()[0]], 'benchmark')


class AccountingTests(unittest.TestCase):
    def test_large_jfr_events_can_cross_stream_chunks_and_truncation_fails(self):
        events = [{'type': 'sample', 'values': {'text': 'escaped " and } and [ ' * 10}},
                  {'type': 'sample2', 'values': {}}]
        encoded = json.dumps({'recording': {'events': events}})
        self.assertEqual(list(jfr_events(io.StringIO(encoded), chunk_size=7)), events)
        with self.assertRaises(ValueError):
            list(jfr_events(io.StringIO(encoded[:-3]), chunk_size=7))

    def test_replicates_have_equal_weight_despite_different_round_counts(self):
        blocks = [{'replicate': 0, 'summary': {'median_ms': x}} for x in (10, 10, 10, 10)]
        blocks.append({'replicate': 1, 'summary': {'median_ms': 30}})
        self.assertEqual(aggregate(blocks, 'median_ms')['median'], 20)
        treatment = [{'replicate': 0, 'summary': {'median_ms': 5}},
                     {'replicate': 1, 'summary': {'median_ms': 15}}]
        result = paired_change(blocks, treatment, 'median_ms')
        self.assertEqual(result['median_percent'], -50)
        with self.assertRaisesRegex(ValueError, 'Unmatched'):
            paired_change(blocks, treatment[:1], 'median_ms')

    def response(self, size=256, cache='HIT'):
        buf = io.BytesIO()
        Image.new('RGB', (size, size), (64, 64, 64)).save(buf, format='PNG')
        return Mock(ok=True, status_code=200, content=buf.getvalue(),
                    headers={'Content-Type': 'image/png', 'geowebcache-cache-result': cache})

    def test_cache_mismatch_is_an_error_and_cannot_inflate_throughput(self):
        session = Mock()
        session.get.return_value = self.response(cache='HIT')
        row = benchmark.request(session, 'http://localhost', {'name': 'test', 'tile': [20, 1, 1]}, 'gwc-miss', 1)
        self.assertEqual(row['error'], 'unexpected_cache_state')
        result = bm.summary([row], 1)
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['successful_requests_per_second'], 0)
        self.assertIsNone(result['median_ms'])

    def test_wrong_png_size_and_xml_exception_are_errors(self):
        session = Mock()
        for response in [self.response(size=255), Mock(ok=True, status_code=200, content=b'<exception/>',
                                                      headers={'Content-Type': 'text/xml'})]:
            session.get.return_value = response
            row = benchmark.request(session, 'http://localhost', {'name': 'test', 'tile': [20, 1, 1]}, 'wms', 0)
            self.assertEqual(row['error'], 'invalid_image_response')

    def test_padded_large_output_retains_resolution_and_crops_for_oracle(self):
        session = Mock()
        session.get.return_value = self.response(size=1026)
        tile = [20, 1, 1]
        row, image = benchmark.request(session, 'http://localhost', {'name': 'test', 'tile': tile},
                                        'wms', 1, 1024, keep_image=True)
        self.assertNotIn('error', row)
        self.assertEqual(image.size, (1024, 1024))
        params = session.get.call_args.kwargs['params']
        bbox = list(map(float, params['bbox'].split(',')))
        original = probe.tile(*tile)
        self.assertAlmostEqual((bbox[2] - bbox[0]) / 1026, (original[2] - original[0]) / 1024)

    def test_failed_requests_remain_in_counts_but_not_successful_latency(self):
        rows = [dict(name='a', seconds=.01, bytes=20, cache=None),
                dict(name='a', seconds=.001, error='bad')]
        result = bm.summary(rows, .02)
        self.assertEqual((result['requests'], result['errors']), (2, 1))
        self.assertEqual(result['median_ms'], 10)
        self.assertEqual(result['successful_requests_per_second'], 50)

    def test_remote_engine_never_reads_local_pid_cgroup(self):
        with patch('affine_fix.benchmark_metrics.lab.owned_container') as inspect:
            self.assertIsNone(bm.cgroup_path({'engine': ['podman', '--connection', 'remote']}))
            inspect.assert_not_called()

    def test_jfr_counts_inclusive_frames_once_and_allocation_weight_per_request(self):
        stack = {'frames': [{'method': {'type': {'name': 'org/geotools/CoverageCrop'}, 'name': 'execute'}}] * 2}
        events = [{'type': 'jdk.ExecutionSample', 'values': {'stackTrace': stack}},
                  {'type': 'jdk.ObjectAllocationSample', 'values': {'stackTrace': stack, 'weight': 1000}},
                  {'type': 'jdk.GarbageCollection', 'values': {}}]
        result = bm.jfr_summary(events, 10)
        self.assertEqual(result['crop_execution_samples'], 1)
        self.assertEqual(result['estimated_allocation_bytes_per_request'], 100)
        self.assertEqual(result['inclusive_allocation_stacks'], [('org.geotools.CoverageCrop.execute', 1000)])
        self.assertEqual(result['leaf_execution_stacks'], [('org.geotools.CoverageCrop.execute', 1)])
        self.assertEqual(result['leaf_allocation_stacks'], [('org.geotools.CoverageCrop.execute', 1000)])


if __name__ == '__main__':
    unittest.main()
