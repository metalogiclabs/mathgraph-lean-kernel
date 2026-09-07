import unittest
from pathlib import Path
from patch_fvar_reuse_v87 import transform, git_blob, BASE

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).parent.parent / 'src/util.rs').read_text()

    def test_actual_frozen_source(self):
        self.assertEqual(git_blob(self.source.encode()), BASE['src/util.rs'])
        out = transform(self.source)
        a = out.index('    pub(crate) fn clear(&mut self) {', out.index("impl<'a, 't> TcCache"))
        b = out.index('    pub(crate) fn clear_session(&mut self)', a)
        self.assertNotIn('self.fvar_cache.clear();', out[a:b])
        self.assertIn('self.ind_occ_cache.clear();', out[a:b])
        original_end = self.source.index('    pub(crate) fn clear_session(&mut self)', self.source.index("impl<'a, 't> TcCache"))
        self.assertEqual(out[b:], self.source[original_end:])

    def test_missing_target_rejected(self):
        with self.assertRaises(ValueError):
            transform(self.source.replace('        self.fvar_cache.clear();\n', '', 1))

    def test_missing_session_invalidation_rejected(self):
        with self.assertRaises(ValueError):
            transform(self.source.replace('        shrink_map(&mut self.fvar_cache);\n', '', 1))

if __name__ == '__main__':
    unittest.main()
