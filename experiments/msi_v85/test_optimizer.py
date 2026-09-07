import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import optimizer as o

class Fake(o.Tournament):
    def __init__(self, root, speeds=None, wrong=False, unstable=False):
        source = Path(root) / 'fixture-source'
        (source / 'src').mkdir(parents=True)
        (source / 'src/eval.rs').write_text('    #[inline]\n    fn spine_snoc_hc(\n    pub(crate) fn eval(&mut self, depth:')
        super().__init__(Path(root) / 'out', source, Path(root), budget=9000)
        self.speeds = speeds or {}
        self.wrong = wrong
        self.unstable = unstable
        self.calls = []
        self.phases = []
    def prepare(self):
        for corpus in o.CORPORA:
            self.replay((), corpus)
    def build(self, recipes):
        recipes = tuple(recipes)
        if recipes not in self.binaries:
            if self.builds >= o.MAX_BUILDS:
                raise o.StopBudget('BUILD_BUDGET_EXHAUSTED')
            self.builds += 1
            p = self.root / 'bin' / (self.key(recipes) + '.bin')
            p.write_text(self.key(recipes))
            self.binaries[recipes] = p
        return self.binaries[recipes]
    def run_binary(self, recipes, corpus, label, compare=True):
        self.build(recipes)
        out = self.root / 'logs' / (label + '.out')
        out.write_bytes(b'wrong' if self.wrong and recipes else b'exact')
        if compare and out.read_bytes() != self.outputs[corpus].read_bytes():
            raise o.Rejected('REPLAY_MISMATCH:' + corpus)
        self.calls.append((recipes, corpus, label))
        value = self.speeds.get(recipes, 1.0)
        if callable(value): value = value(label)
        if self.unstable and '-control' in label: value *= 1.05
        return value, out
    def measure(self, candidate, champion, corpora, passes, phase):
        self.phases.append(phase)
        return super().measure(candidate, champion, corpora, passes, phase)

class Tests(unittest.TestCase):
    def fixture(self, **kwargs):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        return Fake(self.tmp.name, **kwargs)
    def test_exact_anchor(self):
        text = '    #[inline]\n    fn spine_snoc_hc('
        self.assertIn('inline(always)', o.apply_recipes(text, ('spine-inline-always',)))
        with self.assertRaises(o.Rejected):
            o.apply_recipes('different source', ('spine-inline-always',))
        with self.assertRaises(o.Rejected):
            o.apply_recipes(text, ('spine-inline-always', 'spine-inline-never'))
    def test_no_gain_stops_without_full(self):
        t = self.fixture()
        self.assertEqual(t.run(), 0)
        self.assertEqual(t.status, 'NO_PROMOTION')
        self.assertEqual(t.champion, ())
        self.assertFalse(any(p.startswith('full') for p in t.phases))
    def test_replay_mismatch_never_promotes(self):
        t = self.fixture(speeds={(r,): .9 for r in o.RECIPES}, wrong=True)
        self.assertEqual(t.run(), 0)
        self.assertEqual(t.promotions, [])
        self.assertFalse(t.phases)
    def test_requires_independent_confirmation(self):
        t = self.fixture(speeds={('spine-inline-always',): lambda label: 1.03 if label.startswith('confirm') else .95})
        self.assertEqual(t.run(), 0)
        self.assertEqual(t.promotions, [])
        self.assertTrue(any(p.startswith('confirm') for p in t.phases))
    def test_aa_noise_blocks_promotion(self):
        t = self.fixture(speeds={('spine-inline-always',): .90}, unstable=True)
        self.assertEqual(t.run(), 0)
        self.assertEqual(t.promotions, [])
    def test_compounds_only_after_promotion(self):
        t = self.fixture(speeds={('spine-inline-always',): .90,
                                 ('spine-inline-always', 'eval-inline-never'): .80})
        self.assertEqual(t.run(), 0)
        self.assertEqual(t.champion, ('spine-inline-always', 'eval-inline-never'))
        self.assertEqual(len(t.promotions), 2)
        self.assertFalse(any('spine-inline-never' in r and 'spine-inline-always' in r for r in t.binaries))
    def test_budget_cannot_promote(self):
        t = self.fixture()
        with patch.object(o, 'MAX_BUILDS', 1):
            self.assertEqual(t.run(), 0)
        self.assertEqual(t.champion, ())
        self.assertEqual(t.status, 'BUILD_BUDGET_EXHAUSTED')
    def test_promotion_threshold_and_regression(self):
        good = {'geomean': -.02, 'ratios': {'std': .97, 'cedar': .99, 'mathlib': .98}}
        self.assertTrue(o.promotion_ok(good))
        good['ratios']['cedar'] = 1.02
        self.assertFalse(o.promotion_ok(good))
    def test_summary_and_ledger_survive_negative(self):
        t = self.fixture()
        t.run()
        self.assertEqual(__import__('json').loads((t.root/'summary.json').read_text())['status'], 'NO_PROMOTION')
        self.assertIn('finish', (t.root/'ledger.jsonl').read_text())
    def test_full_evaluation_budget_is_global(self):
        t = self.fixture(speeds={('spine-inline-always',): .90,
                                 ('spine-inline-always', 'eval-inline-never'): .80})
        with patch.object(o, 'MAX_FULL', 1):
            self.assertEqual(t.run(), 0)
        self.assertEqual(t.champion, ('spine-inline-always',))
        self.assertEqual(t.full_evaluations, 1)
        self.assertEqual(t.status, 'FULL_EVALUATION_BUDGET_EXHAUSTED')
    def test_candidate_runtime_failure_is_rejected(self):
        t = self.fixture()
        t.build(('spine-inline-always',))
        with patch.object(t, 'command', side_effect=o.Infrastructure('COMMAND_FAILED:bad')):
            with self.assertRaises(o.Rejected):
                o.Tournament.run_binary(t, ('spine-inline-always',), 'std', 'bad')
    def test_baseline_runtime_failure_is_infrastructure(self):
        t = self.fixture()
        t.build(())
        with patch.object(t, 'command', side_effect=o.Infrastructure('COMMAND_FAILED:bad')):
            with self.assertRaises(o.Infrastructure):
                o.Tournament.run_binary(t, (), 'std', 'bad')

if __name__ == '__main__': unittest.main(verbosity=2)
