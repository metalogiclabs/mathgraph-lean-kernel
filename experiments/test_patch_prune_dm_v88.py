import unittest
from pathlib import Path
from patch_prune_dm_v88 import transform, blob, BASE, NEEDLE, REPLACEMENT

class PatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path('src/util.rs').read_text()
        assert blob(cls.source.encode()) == BASE

    def test_exact_real_source(self):
        out = transform(self.source)
        self.assertEqual(out.replace(REPLACEMENT, NEEDLE), self.source)
        self.assertEqual(out.count(NEEDLE), 1)
        self.assertEqual(out.count('self.fvar_cache.clear();'), self.source.count('self.fvar_cache.clear();'))

    def test_reject_missing_reset(self):
        with self.assertRaises(AssertionError): transform(self.source.replace(NEEDLE, '', 1))

    def test_reject_missing_session_invalidation(self):
        with self.assertRaises(AssertionError):
            transform(self.source.replace(NEEDLE, '', 1).replace('self.prune_dm.fill((0, 0, None));', '', 1))

    def test_reject_duplicate_reset(self):
        with self.assertRaises(AssertionError):
            transform(self.source.replace(NEEDLE, NEEDLE + NEEDLE, 1))

if __name__ == '__main__': unittest.main()
