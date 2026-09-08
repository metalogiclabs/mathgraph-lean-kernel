#!/usr/bin/env python3
"""Install one source-guarded, reusable inline-spine materialization rule."""
import hashlib
from pathlib import Path
import sys

BASE = '0da9d0cf8c16cc3b13ef04cc827ed26b2813477a'
OLD = '''    pub fn to_vec<'b>(&'b self) -> Vec<&'b Elim<'a>> {
        let len = self.len() as usize;
        let mut out = Vec::with_capacity(len);
'''
NEW = '''    pub fn to_vec<'b>(&'b self) -> smallvec::SmallVec<[&'b Elim<'a>; 8]> {
        let len = self.len() as usize;
        let mut out = smallvec::SmallVec::with_capacity(len);
'''

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def transform(source):
    assert source.count(OLD) == 1, 'unexpected materialization grammar'
    return source.replace(OLD, NEW)

def apply(root, with_tests=False):
    p = Path(root) / 'src/value.rs'
    original = p.read_bytes()
    assert blob(original) == BASE, 'frozen source mismatch'
    revised = transform(original.decode()).encode()
    assert revised.replace(NEW.encode(), OLD.encode()) == original
    p.write_bytes(revised)
    if with_tests:
        tests = Path(root) / 'src/tests.rs'
        old_tests = tests.read_bytes()
        assert blob(old_tests) == '2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc'
        tests.write_bytes(old_tests + b'mod spine_v90;\n')
        target = Path(root) / 'src/tests/spine_v90.rs'
        target.write_bytes((Path(__file__).parent / 'spine_v90.rs').read_bytes())
    print('V90_SOURCE_GUARD=PASS')
    print('V90_EXACT_SOURCE_ABLATION=PASS')
    print('V90_PRODUCTION_CHANGE=inline_spine_materialization_only')

if __name__ == '__main__':
    apply(sys.argv[1], '--with-tests' in sys.argv[2:])
