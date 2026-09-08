import tempfile
import unittest
from pathlib import Path
from patch_spine_v90 import BASE, OLD, NEW, blob, transform, apply

class SpineRuleTests(unittest.TestCase):
    def test_exact_reversible_transformation(self):
        original = Path(__file__).resolve().parents[1].joinpath('src/value.rs').read_bytes()
        self.assertEqual(blob(original), BASE)
        changed = transform(original.decode()).encode()
        self.assertNotEqual(changed, original)
        self.assertEqual(changed.replace(NEW.encode(), OLD.encode()), original)
        self.assertEqual(changed.count(NEW.encode()), 1)
    def test_rejects_unexpected_grammar(self):
        with self.assertRaises(AssertionError):
            transform('')
        with self.assertRaises(AssertionError):
            transform(OLD + OLD)
    def test_rejects_source_change(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'src/value.rs'
            p.parent.mkdir()
            p.write_text('not the frozen source')
            with self.assertRaises(AssertionError):
                apply(d)

if __name__ == '__main__':
    unittest.main()
