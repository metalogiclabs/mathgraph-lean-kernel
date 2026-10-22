import importlib.util
import json
from decimal import Decimal as D
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name('analyze_phases.py')


class PhaseArithmetic(unittest.TestCase):
    def helper(self, name):
        self.assertTrue(MODULE.is_file(), 'phase analysis helper is missing')
        spec = importlib.util.spec_from_file_location('phase_analysis', MODULE)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, name, None)), 'missing arithmetic: ' + name)
        return getattr(module, name)

    def test_promotion_is_nested_and_disjoint_partition_reconstructs_actual_apply(self):
        timings = dict(producer_seconds=D('.1'), consumer_seconds=D('.9'), end_to_end_seconds=D('1.05'),
            baseline_validation_seconds=D('.1'), identity_update_seconds=D('.1'),
            materialization_and_hash_seconds=D('.2'), checking_seconds=D('.1'),
            persistence_seconds=D('.3'), chain_promotion_seconds=D('.2'))
        result = self.helper('partition_wall')(timings)
        self.assertEqual(result['named_disjoint_sum_seconds'], D('.9'))
        self.assertEqual(result['consumer_unclassified_seconds'], D('.1'))
        self.assertEqual(result['apply_unclassified_seconds'], D('.05'))
        self.assertEqual(result['reconstructed_apply_seconds'], D('1.05'))
        self.assertEqual(result['receipt_persistence_before_promotion_seconds'], D('.1'))

    def test_negative_residuals_are_preserved_without_causal_attribution(self):
        timings = dict(producer_seconds=D('.1'), consumer_seconds=D('.1'), end_to_end_seconds=D('.2'),
            baseline_validation_seconds=D('.1'), identity_update_seconds=D('.1'),
            materialization_and_hash_seconds=D('.1'), checking_seconds=D('.1'),
            persistence_seconds=D('.1'), chain_promotion_seconds=D('.1'))
        result = self.helper('partition_wall')(timings)
        self.assertEqual(result['consumer_unclassified_seconds'], D('-.4'))
        self.assertTrue(result['has_negative_residual'])

    def test_sequence_total_summary_never_adds_phase_medians(self):
        summarize = self.helper('statistics')
        self.assertEqual(summarize([D('101'), D('101'), D('2')])['median'], D('101'))
        self.assertEqual(summarize([D('1'), D('100'), D('1')])['median'], D('1'))
        self.assertEqual(summarize([D('100'), D('1'), D('1')])['median'], D('1'))

    def test_decimal_addition_preserves_small_recorded_residual(self):
        self.assertEqual(self.helper('total')([D('1'), D('1e-50')]), D('1.' + '0' * 49 + '1'))

    def test_memory_samples_are_never_summed_into_a_memory_quantity(self):
        rows = [dict(revision=1, raw_memory=dict(persistence=dict(processes=dict(adapter=dict(VmRSS=10, VmHWM=20)))))]
        observed = self.helper('memory_summary')(rows)['observed_sample_statistics']['adapter']['VmRSS']
        self.assertNotIn('sum', observed)

    def test_interleaved_bytes_keep_their_own_observed_source(self):
        fixture = Path('/workspace/kernel-audit/revision-lifecycle/harness/smoke-continuous-final/summary.json')
        report = json.loads(fixture.read_text(), parse_float=D)
        pair = report['profiles']['original']['pairs'][0]
        pair['steps'][0]['receipt_audit']['delta_bytes'] = 999
        analyzed = self.helper('pair_analysis')('original', pair, 1, 1)
        self.assertEqual(analyzed['interleaved']['rows'][0]['delta_bytes'], 999)
        self.assertIsNone(analyzed['interleaved']['rows'][0]['full_export_disk_bytes_written'])


if __name__ == '__main__':
    unittest.main()
