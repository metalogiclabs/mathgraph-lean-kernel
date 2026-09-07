#!/usr/bin/env python3
"""Frozen, one-statement experiment: retain the structural prune memo within a session."""
import hashlib
from pathlib import Path
import sys

BASE = 'a0fab9f758a6fe947585d866d98665d9512c1a2c'
NEEDLE = '        self.prune_dm.fill((0, 0, None));\n'
REPLACEMENT = ('        // The direct prune memo is structural and its arena remains live.\n'
               '        // Keep it across declaration resets; clear_session still invalidates it.\n')

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def transform(source):
    anchor = "impl<'a, 't> TcCache<'a, 't> {"
    start = source.index('    pub(crate) fn clear(&mut self) {', source.index(anchor))
    end = source.index('    pub(crate) fn clear_session(&mut self)', start)
    old = source[start:end]
    assert old.count(NEEDLE) == 1
    assert source[end:].count(NEEDLE) == 1
    new = old.replace(NEEDLE, REPLACEMENT)
    assert new.replace(REPLACEMENT, NEEDLE) == old
    return source[:start] + new + source[end:]

def apply(root, with_tests=True):
    root = Path(root)
    p = root/'src/util.rs'
    assert blob(p.read_bytes()) == BASE, 'frozen util.rs mismatch'
    assert blob((root/'src/eval.rs').read_bytes()) == 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
    p.write_text(transform(p.read_text()))
    if with_tests:
        tests = root/'src/tests.rs'
        assert blob(tests.read_bytes()) == '2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc'
        tests.write_text(tests.read_text() + 'mod prune_dm_v88;\n')
    print('V88_SOURCE_GUARD=PASS')
    print('V88_PRODUCTION_CHANGE=retain_prune_dm_until_clear_session_ONLY')

if __name__ == '__main__':
    apply(sys.argv[1], '--no-tests' not in sys.argv[2:])
