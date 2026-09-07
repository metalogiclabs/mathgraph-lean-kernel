import unittest
from patch_cache_reset_v86 import FIELDS, SETS, FRAMES, transform

def fixture():
    decls = '\n'.join('    pub(crate) '+f+': '+('FxHashSet' if f in SETS else 'FxHashMap')+'<usize, bool>,' for f in FIELDS if f!='frames')
    clear = '\n'.join('        self.'+f+'.clear();' for f in FIELDS)
    return ("impl<'a, 't> TcCache<'a, 't> {\n" + decls + '\n'
        '    pub(crate) fn clear(&mut self) {\n' + clear + '\n        self.prune_dm.fill((0, 0, None));\n    }\n'
        '    pub(crate) fn clear_session(&mut self) {\n' + FRAMES + '\n    }\n}\n\npub(crate) const KEEP_CAP: usize = 1 << 15;\n')

class PatchTests(unittest.TestCase):
    def test_exact_coverage(self):
        out = transform(fixture())
        self.assertEqual(out.count('shrink_map(&mut self.'), 26)
        self.assertEqual(out.count('shrink_set(&mut self.'), 5)
        self.assertIn(FRAMES, out)
        self.assertEqual(out.count('self.prune_dm.fill((0, 0, None));'), 1)
    def test_wrong_type_rejected(self):
        with self.assertRaises(ValueError):
            transform(fixture().replace('fvar_cache: FxHashMap', 'fvar_cache: FxHashSet'))
    def test_missing_field_rejected(self):
        with self.assertRaises(ValueError):
            transform(fixture().replace('        self.fvar_cache.clear();\n', ''))
    def test_unexpected_statement_rejected(self):
        with self.assertRaises(ValueError):
            transform(fixture().replace('        self.fvar_cache.clear();', '        self.fvar_cache.clear();\n        self.probe_depth = 0;'))

if __name__ == '__main__':
    unittest.main()
