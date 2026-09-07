#!/usr/bin/env python3
"""Apply the exact v85 reset experiment with type and source guards."""
import argparse
import hashlib
import re
from pathlib import Path

BASE_BLOB = 'a0fab9f758a6fe947585d866d98665d9512c1a2c'
FIELDS = '''unfold_const_cache rec_rule_cache const_head_type_cache const_head_value_cache const_result_level_cache conv_cache_pos conv_cache_neg conv_cache_neg_probe frames lsub_bases level_subs type_cache thunk_hc quote_cache open_eval_cache open_eval_seen bvar_hc spine_hc lam_hc pi_hc rigid_hc unfold_hc iota_stuck struct_eta_cache iota_cache canon_cache content_hc fvar_cache ind_occ_cache closed_eval_cache lam_domain_cache global_value_cache'''.split()
SETS = set('conv_cache_pos conv_cache_neg conv_cache_neg_probe open_eval_seen iota_stuck'.split())
FRAMES = '''        if self.frames.capacity() > KEEP_CAP {
            self.frames = hashbrown::HashTable::new();
        } else {
            self.frames.clear();
        }'''
TESTS = r'''
#[cfg(test)]
mod cache_reset_preflight_v86 {
    use super::*;

    #[test]
    fn clears_maps_sets_and_prune_entries() {
        let arena = bumpalo::Bump::new();
        let mut cache = TcCache::new(&arena);
        cache.fvar_cache.insert(1, true);
        cache.ind_occ_cache.insert(2, false);
        cache.conv_cache_pos.insert((1, 2));
        cache.conv_cache_neg.insert((3, 4));
        cache.iota_stuck.insert(7);
        cache.prune_dm[0] = (1, 2, Some(cache.empty_env));
        cache.clear();
        assert!(cache.fvar_cache.is_empty());
        assert!(cache.ind_occ_cache.is_empty());
        assert!(cache.conv_cache_pos.is_empty());
        assert!(cache.conv_cache_neg.is_empty());
        assert!(cache.iota_stuck.is_empty());
        assert_eq!(cache.prune_dm[0].0, 0);
        assert_eq!(cache.prune_dm[0].1, 0);
        assert!(cache.prune_dm[0].2.is_none());
        cache.fvar_cache.insert(1, false);
        assert_eq!(cache.fvar_cache.get(&1), Some(&false));
        cache.clear();
        assert!(cache.fvar_cache.get(&1).is_none());
    }

    #[test]
    fn oversized_map_is_released_and_reusable() {
        let arena = bumpalo::Bump::new();
        let mut cache = TcCache::new(&arena);
        for i in 0..=KEEP_CAP {
            cache.fvar_cache.insert(i, true);
        }
        assert!(cache.fvar_cache.capacity() > KEEP_CAP);
        cache.clear();
        assert!(cache.fvar_cache.is_empty());
        assert!(cache.fvar_cache.capacity() <= KEEP_CAP);
        cache.fvar_cache.insert(1, false);
        assert_eq!(cache.fvar_cache.get(&1), Some(&false));
    }
}
'''

def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def transform(source):
    anchor = "impl<'a, 't> TcCache<'a, 't> {"
    start = source.index(anchor)
    a = source.index('    pub(crate) fn clear(&mut self) {', start)
    b = source.index('    pub(crate) fn clear_session(&mut self)', a)
    old = source[a:b]
    names = re.findall(r'\bself\.(\w+)\.clear\(\);', old)
    if names != FIELDS:
        raise ValueError('unexpected cache reset field list')
    declarations = dict(re.findall(r'^\s*pub\(crate\) (\w+): (FxHashMap|FxHashSet)<', source[:a], re.M))
    if any(declarations.get(f) != ('FxHashSet' if f in SETS else 'FxHashMap') for f in FIELDS if f != 'frames'):
        raise ValueError('cache field types do not match the verified source')
    session = source[b:source.index('\n}\n\npub(crate) const KEEP_CAP', b)]
    if FRAMES not in session:
        raise ValueError('bounded frame reset is not the frozen implementation')
    lines = old.splitlines(keepends=True)
    out = []
    for line in lines:
        m = re.fullmatch(r'(\s*)self\.(\w+)\.clear\(\);\n', line)
        if m:
            indent, field = m.groups()
            if field == 'frames':
                out.append(FRAMES + '\n')
            else:
                out.append(f'{indent}{"shrink_set" if field in SETS else "shrink_map"}(&mut self.{field});\n')
        else:
            if line.strip() not in ('pub(crate) fn clear(&mut self) {', '}', 'self.prune_dm.fill((0, 0, None));'):
                raise ValueError('unexpected statement in cache reset')
            out.append(line)
    replacement = ''.join(out)
    if replacement.count('self.prune_dm.fill((0, 0, None));') != 1:
        raise ValueError('prune invalidation changed')
    if len(re.findall(r'\bshrink_(?:map|set)\(&mut self\.', replacement)) != len(FIELDS)-1:
        raise ValueError('cache reset coverage changed')
    return source[:a] + replacement + source[b:]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('--tests', action='store_true')
    args = ap.parse_args()
    raw = args.source.read_bytes()
    if git_blob(raw) != BASE_BLOB:
        raise SystemExit('SOURCE_MISMATCH: frozen util.rs blob required')
    out = transform(raw.decode())
    if args.tests:
        out += TESTS
    args.source.write_text(out)
    print('V86_SOURCE_GUARD=PASS')
    print('V86_TYPED_RESET_FIELDS=32')
    print('V86_PRODUCTION_CHANGE=TcCache.clear_ONLY')

if __name__ == '__main__':
    main()
