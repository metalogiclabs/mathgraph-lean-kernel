"""Independent arithmetic mutations against actual small lifecycle evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
FIXTURE = Path('/workspace/kernel-audit/revision-lifecycle/harness/smoke-continuous-final/summary.json')


class EconomicEvidenceTests(unittest.TestCase):
    def helper(self):
        path = HERE / 'economics.py'
        self.assertTrue(path.is_file(), 'missing independent arithmetic verifier')
        spec = importlib.util.spec_from_file_location('independent_economics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self):
        return json.loads(FIXTURE.read_bytes())

    def test_actual_smoke_arithmetic_and_all_bootstraps(self):
        result = self.helper().validate_economics(self.fixture())
        self.assertEqual(result['profiles'], 2)
        self.assertEqual(result['pairs'], 2)
        self.assertEqual(result['accepted_revisions'], 8)
        self.assertEqual(result['economic_series'], 16)

    def test_real_summary_mutations_are_rejected(self):
        helper = self.helper()
        for label, mutate in (
            ('wrong confidence', lambda p: p['economics']['bootstrap_ratio_interval_95'].__setitem__(1, 0.001)),
            ('fake speedup', lambda p: p['economics'].__setitem__('status', 'SPEEDUP')),
            ('missing setup cost', lambda p: p['pairs'][0]['components'].__setitem__('api_component_sum_wall_seconds', 0.5)),
            ('negative direct cpu', lambda p: p['pairs'][0]['genesis']['direct_rust'].__setitem__('completed_child_cpu_seconds', -1)),
            ('boolean duration', lambda p: p['pairs'][0]['steps'][0].__setitem__('apply_wall_seconds', True)),
            ('nonfinite duration', lambda p: p['pairs'][0]['steps'][0].__setitem__('apply_cpu_seconds', float('nan'))),
            ('missing continuous command', lambda p: p['pairs'][0]['continuous']['direct']['commands'].pop()),
            ('impossible continuous interval', lambda p: p['pairs'][0]['continuous']['direct'].__setitem__('wall_seconds', 0.000001)),
            ('wrong continuous order', lambda p: p['pairs'][0]['continuous'].__setitem__('order', ['direct', 'candidate'])),
            ('scope substitution', lambda p: p['economics'].__setitem__('setup_in_timed_update', False)),
        ):
            with self.subTest(label=label):
                report = self.fixture()
                mutate(report['profiles']['original'])
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    helper.validate_economics(report)

    def test_known_constant_bootstrap_has_exact_bounds(self):
        result = self.helper().paired_statistics([0.5] * 5, [1.0] * 5, seed=20261024)
        self.assertEqual(result['bootstrap_ratio_interval_95'], [0.5, 0.5])
        self.assertEqual(result['paired_wins'], 5)
        self.assertEqual(result['median_ratio'], 0.5)
        self.assertEqual(result['status'], 'SPEEDUP')
        self.assertTrue(result['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
