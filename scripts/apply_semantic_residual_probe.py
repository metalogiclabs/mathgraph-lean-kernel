#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'eval.rs'
s = p.read_text()

anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::sync::atomic::{AtomicU64, Ordering};

static MG_FORCE_ALL_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_FORCE_ALL_STORE_HITS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_STUCK_HITS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_CACHE_HITS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_FRESH: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_RECURSOR: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_QUOT: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_K_SUCCESS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_DESCEND: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_FIRE_SUCCESS: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_FIRE_FAIL: AtomicU64 = AtomicU64::new(0);

#[inline]
fn mg_inc(x: &AtomicU64) { x.fetch_add(1, Ordering::Relaxed); }

pub fn report_residual_stats() {
    if std::env::var_os("MATHGRAPH_RESIDUAL_PROBE").is_none() { return; }
    eprintln!(
        "MATHGRAPH_RESIDUAL force_all_calls={} force_all_store_hits={} iota_calls={} iota_stuck_hits={} iota_cache_hits={} iota_fresh={} iota_recursor={} iota_quot={} iota_k_success={} iota_descend={} iota_fire_success={} iota_fire_fail={}",
        MG_FORCE_ALL_CALLS.load(Ordering::Relaxed),
        MG_FORCE_ALL_STORE_HITS.load(Ordering::Relaxed),
        MG_IOTA_CALLS.load(Ordering::Relaxed),
        MG_IOTA_STUCK_HITS.load(Ordering::Relaxed),
        MG_IOTA_CACHE_HITS.load(Ordering::Relaxed),
        MG_IOTA_FRESH.load(Ordering::Relaxed),
        MG_IOTA_RECURSOR.load(Ordering::Relaxed),
        MG_IOTA_QUOT.load(Ordering::Relaxed),
        MG_IOTA_K_SUCCESS.load(Ordering::Relaxed),
        MG_IOTA_DESCEND.load(Ordering::Relaxed),
        MG_IOTA_FIRE_SUCCESS.load(Ordering::Relaxed),
        MG_IOTA_FIRE_FAIL.load(Ordering::Relaxed),
    );
}
'''
if insert not in s:
    assert anchor in s
    s = s.replace(anchor, anchor + insert, 1)

old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }'''
new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        mg_inc(&MG_FORCE_ALL_CALLS);\n        if let Some(r) = self.store_lookup(depth, v) {\n            mg_inc(&MG_FORCE_ALL_STORE_HITS);\n            return r;\n        }'''
assert old in s
s = s.replace(old, new, 1)

old = '''    fn iota_step(&mut self, depth: u32, v: V<'t>) -> ForceStep<'t> {\n        let key = v as *const Value<'t> as usize;\n        if self.tc_cache.iota_stuck.contains(&key) {\n            return ForceStep::Done;\n        }\n        if let Some(c) = self.tc_cache.iota_cache.get(&key) {\n            return ForceStep::Reduced(c);\n        }\n        match v {'''
new = '''    fn iota_step(&mut self, depth: u32, v: V<'t>) -> ForceStep<'t> {\n        mg_inc(&MG_IOTA_CALLS);\n        let key = v as *const Value<'t> as usize;\n        if self.tc_cache.iota_stuck.contains(&key) {\n            mg_inc(&MG_IOTA_STUCK_HITS);\n            return ForceStep::Done;\n        }\n        if let Some(c) = self.tc_cache.iota_cache.get(&key) {\n            mg_inc(&MG_IOTA_CACHE_HITS);\n            return ForceStep::Reduced(c);\n        }\n        mg_inc(&MG_IOTA_FRESH);\n        match v {'''
assert old in s
s = s.replace(old, new, 1)

old = '''            Value::Rigid { head: RigidHead::Recursor(name, levels), spine , ..} => {\n                let env = self.env;'''
new = '''            Value::Rigid { head: RigidHead::Recursor(name, levels), spine , ..} => {\n                mg_inc(&MG_IOTA_RECURSOR);\n                let env = self.env;'''
assert old in s
s = s.replace(old, new, 1)

old = '''                if let Some(r) = self.k_pre_reduce(depth, &rec, *levels, &args) {\n                    self.tc_cache.iota_cache.insert(key, r);\n                    return ForceStep::Reduced(r);\n                }'''
new = '''                if let Some(r) = self.k_pre_reduce(depth, &rec, *levels, &args) {\n                    mg_inc(&MG_IOTA_K_SUCCESS);\n                    self.tc_cache.iota_cache.insert(key, r);\n                    return ForceStep::Reduced(r);\n                }'''
assert old in s
s = s.replace(old, new, 1)

old = '''                if self.is_iota_reducible(major_h) {\n                    return ForceStep::Descend(major_h);\n                }\n                match self.fire_recursor(depth, &rec, *levels, &args, major_h) {\n                    Some(res) => {\n                        self.tc_cache.iota_cache.insert(key, res);\n                        ForceStep::Reduced(res)\n                    }\n                    None => {\n                        self.tc_cache.iota_stuck.insert(key);\n                        ForceStep::Done\n                    }'''
new = '''                if self.is_iota_reducible(major_h) {\n                    mg_inc(&MG_IOTA_DESCEND);\n                    return ForceStep::Descend(major_h);\n                }\n                match self.fire_recursor(depth, &rec, *levels, &args, major_h) {\n                    Some(res) => {\n                        mg_inc(&MG_IOTA_FIRE_SUCCESS);\n                        self.tc_cache.iota_cache.insert(key, res);\n                        ForceStep::Reduced(res)\n                    }\n                    None => {\n                        mg_inc(&MG_IOTA_FIRE_FAIL);\n                        self.tc_cache.iota_stuck.insert(key);\n                        ForceStep::Done\n                    }'''
assert old in s
s = s.replace(old, new, 1)

# Count Quot branch and its descend/success/fail separately into the shared totals.
old = '''            Value::Rigid { head: RigidHead::QuotConst(name, _), spine , ..} => {\n                let args = self.spine_apps(depth, spine);'''
new = '''            Value::Rigid { head: RigidHead::QuotConst(name, _), spine , ..} => {\n                mg_inc(&MG_IOTA_QUOT);\n                let args = self.spine_apps(depth, spine);'''
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s)

m = root / 'src' / 'main.rs'
t = m.read_text()
anchor = '    match out {\n'
replacement = '    sokonanoda::eval::report_residual_stats();\n    match out {\n'
assert anchor in t
if replacement not in t:
    t = t.replace(anchor, replacement, 1)
m.write_text(t)
print('semantic residual probe applied')
