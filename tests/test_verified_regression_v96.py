"""Fast, dependency-free checks for the v96 experimental driver.

The finite model checks the empty-environment observation only. It is not a
proof of the Rust implementation or a replacement for external kernel replay.
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiments import verified_regression_v96 as v


class DriverTests(unittest.TestCase):
    def test_replacement_is_exact_and_fail_closed(self):
        original = 'prefix\n' + v.OLD + 'suffix\n'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'eval.rs'
            path.write_text(original)
            raw = original.encode()
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            with patch.object(v, 'SOURCE_BLOB', blob):
                digest = v.apply_candidate(path)
                self.assertEqual(path.read_text(), original.replace(v.OLD, v.NEW))
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
                with self.assertRaises(AssertionError):
                    v.apply_candidate(path)
        for text in ('missing', v.OLD + v.OLD):
            with self.assertRaises(AssertionError):
                v.replace_once(text, v.OLD, v.NEW)

    def test_probe_conservation_and_negative_controls(self):
        good = dict(cold=10, framed=4, one_cons=3, other_cons=3, nil=0,
                    empty=3, empty_framed=1, empty_cons=2)
        self.assertEqual(v.validate_probe(good), good)
        for change in (dict(cold=11), dict(empty=4), dict(empty_cons=3),
                       dict(framed=11), dict(nil=-1), dict(cold=True),
                       dict(empty_framed=5)):
            bad = dict(good, **change)
            with self.assertRaises(AssertionError):
                v.validate_probe(bad)

    def test_subprocess_reads_input_and_checks_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / 'echo.py'
            inp = root / 'input.ndjson'
            inp.write_bytes(b'one\ntwo\n')
            script.write_text('import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n')
            result = v.run_binary(sys.executable, script, inp,
                                  subprocess.PIPE, subprocess.PIPE)
            self.assertEqual(result.stdout, inp.read_bytes())
            self.assertEqual(result.returncode, 0)
            script.write_text('import sys\nsys.exit(2)\n')
            with self.assertRaises(subprocess.CalledProcessError):
                v.run_binary(sys.executable, script, inp)

    def test_empty_representation_model(self):
        # All four-position partial environments over a two-element carrier.
        # A frame with no retained slots and Nil agree on lookup, length and
        # universe-substitution identity; nonempty results are left unchanged.
        from itertools import product
        cases = 0
        for slots in product((None, 0, 1), repeat=4):
            for requested in range(16):
                retained = tuple(x if requested & (1 << i) else None
                                 for i, x in enumerate(slots))
                mask = sum(1 << i for i, x in enumerate(retained) if x is not None)
                for lsub in (None, 'substitution'):
                    old = ('Framed', mask, retained, lsub)
                    new = ('Nil', 0, (None,) * 4, lsub) if mask == 0 else old
                    self.assertEqual(old[1], new[1])
                    self.assertEqual(old[2], new[2])
                    self.assertEqual(old[3], new[3])
                    cases += 1
        self.assertEqual(cases, 2592)


if __name__ == '__main__':
    unittest.main()
