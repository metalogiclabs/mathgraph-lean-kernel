#!/usr/bin/env python3
import hashlib,re,sys
from pathlib import Path
BASE='a0fab9f758a6fe947585d866d98665d9512c1a2c'
CANDIDATE='714c9a11204f25e0f357ef161c86391cc85bb7bd'
EMAP=['unfold_const_cache','rec_rule_cache','const_head_type_cache','const_head_value_cache','const_result_level_cache','closed_eval_cache','lam_domain_cache','global_value_cache','open_eval_cache','type_cache','quote_cache','unfold_hc','struct_eta_cache','iota_cache','canon_cache','content_hc','fvar_cache','ind_occ_cache']
ESET=['conv_cache_pos','conv_cache_neg']
BLOCK='''\npub(crate) struct EpochMap<K, V> {\n    map: FxHashMap<K, (u32, V)>,\n    epoch: u32,\n}\nimpl<K: Eq + Hash, V> EpochMap<K, V> {\n    fn new() -> Self { Self { map: FxHashMap::default(), epoch: 1 } }\n    #[inline]\n    pub(crate) fn get(&self, key: &K) -> Option<&V> {\n        self.map.get(key).and_then(|(e, v)| (*e == self.epoch).then_some(v))\n    }\n    #[inline]\n    pub(crate) fn insert(&mut self, key: K, value: V) -> Option<V> {\n        self.map.insert(key, (self.epoch, value)).and_then(|(e, v)| (e == self.epoch).then_some(v))\n    }\n    #[inline]\n    fn advance(&mut self) {\n        self.epoch = self.epoch.wrapping_add(1);\n        if self.epoch == 0 { self.map.clear(); self.epoch = 1; }\n    }\n    fn reset(&mut self) {\n        if self.map.capacity() > KEEP_CAP { self.map = FxHashMap::default(); } else { self.map.clear(); }\n        self.epoch = 1;\n    }\n}\npub(crate) struct EpochSet<K> {\n    map: FxHashMap<K, u32>,\n    epoch: u32,\n}\nimpl<K: Eq + Hash> EpochSet<K> {\n    fn new() -> Self { Self { map: FxHashMap::default(), epoch: 1 } }\n    #[inline]\n    pub(crate) fn contains(&self, key: &K) -> bool { self.map.get(key).copied() == Some(self.epoch) }\n    #[inline]\n    pub(crate) fn insert(&mut self, key: K) -> bool {\n        let old = self.map.insert(key, self.epoch); old != Some(self.epoch)\n    }\n    #[inline]\n    fn advance(&mut self) {\n        self.epoch = self.epoch.wrapping_add(1);\n        if self.epoch == 0 { self.map.clear(); self.epoch = 1; }\n    }\n    fn reset(&mut self) {\n        if self.map.capacity() > KEEP_CAP { self.map = FxHashMap::default(); } else { self.map.clear(); }\n        self.epoch = 1;\n    }\n}\n\n'''
def blob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def transform(s):
    s=s.replace('pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;\n',BLOCK+'pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;\n')
    for n in EMAP: s=re.sub(rf'(pub\(crate\) {n}: )FxHashMap<([^;]+)>;',rf'\1EpochMap<\2>;',s)
    for n in ESET: s=re.sub(rf'(pub\(crate\) {n}: )FxHashSet<([^;]+)>;',rf'\1EpochSet<\2>;',s)
    for n in EMAP: s=re.sub(rf'({n}: )(?:session_small_fx_hash_map|session_fx_hash_map|small_fx_hash_map|new_fx_hash_map)\(\),',rf'\1EpochMap::new(),',s)
    for n in ESET: s=re.sub(rf'({n}: )(?:session_small_fx_hash_set|session_fx_hash_set|small_fx_hash_set)\(\),',rf'\1EpochSet::new(),',s)
    a=s.index('    pub(crate) fn clear(&mut self) {'); b=s.index('    pub(crate) fn clear_session(&mut self)',a); p=s[a:b]
    for n in EMAP+ESET: p=p.replace(f'self.{n}.clear();',f'self.{n}.advance();')
    s=s[:a]+p+s[b:]
    a=s.index('    pub(crate) fn clear_session(&mut self)'); b=s.index('\n    }\n}',a); p=s[a:b]
    for n in EMAP: p=re.sub(rf'shrink_map\(&mut self\.{n}\);',f'self.{n}.reset();',p)
    for n in ESET: p=re.sub(rf'shrink_set\(&mut self\.{n}\);',f'self.{n}.reset();',p)
    return s[:a]+p+s[b:]
def main(root):
    root=Path(root); p=root/'src/util.rs'; raw=p.read_bytes(); assert blob(raw)==BASE,blob(raw)
    out=transform(raw.decode()); assert blob(out.encode())==CANDIDATE,blob(out.encode()); p.write_text(out)
    assert blob((root/'src/tests.rs').read_bytes())=='2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc'
    print('V91_SOURCE_GUARD=PASS'); print('V91_PRODUCTION_CHANGE=epoch_invalidation_for_get_insert_caches')
if __name__=='__main__': main(sys.argv[1])
