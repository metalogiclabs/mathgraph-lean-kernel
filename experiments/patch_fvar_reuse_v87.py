#!/usr/bin/env python3
"""Apply the one-field, session-scoped cache-reuse experiment to frozen source."""
import hashlib
import pathlib
import sys

BASE = {
    'src/util.rs': 'a0fab9f758a6fe947585d866d98665d9512c1a2c',
    'src/tests.rs': '2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc',
}

def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def transform(source):
    anchor = "impl<'a, 't> TcCache<'a, 't> {"
    start = source.index('    pub(crate) fn clear(&mut self) {', source.index(anchor))
    end = source.index('    pub(crate) fn clear_session(&mut self)', start)
    old = source[start:end]
    needle = '        self.fvar_cache.clear();\n'
    if old.count(needle) != 1 or old.count('        self.ind_occ_cache.clear();\n') != 1:
        raise ValueError('unexpected per-declaration cache reset')
    replacement = ('        // This memo is structural after force_thunk and has no environment or\n'
                   '        // haystack dependency. Keep it only until clear_session, before\n'
                   '        // SessionBump storage can be recycled.\n')
    new = old.replace(needle, replacement)
    if new.replace(replacement, needle) != old:
        raise ValueError('unexpected production change')
    if source[end:].count('shrink_map(&mut self.fvar_cache);') != 1:
        raise ValueError('session invalidation is missing')
    return source[:start] + new + source[end:]

def apply(root):
    root = pathlib.Path(root)
    for name, expected in BASE.items():
        data = (root / name).read_bytes()
        if git_blob(data) != expected:
            raise ValueError(f'{name}: frozen source mismatch')
    util = root / 'src/util.rs'
    tests = root / 'src/tests.rs'
    util.write_text(transform(util.read_text()))
    tests.write_text(tests.read_text() + 'mod fvar_reuse_v87;\n')
    print('V87_SOURCE_GUARD=PASS')
    print('V87_PRODUCTION_CHANGE=fvar_cache_retained_until_clear_session_ONLY')

if __name__ == '__main__':
    apply(sys.argv[1])
