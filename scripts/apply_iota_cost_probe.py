#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'eval.rs'
s = p.read_text()

anchor = 'use std::collections::hash_map::Entry;\n'
probe = '''use std::sync::atomic::{AtomicU64, Ordering};
static MG_FIRE: AtomicU64 = AtomicU64::new(0);
static MG_RULE_HIT: AtomicU64 = AtomicU64::new(0);
static MG_RULE_MISS: AtomicU64 = AtomicU64::new(0);
static MG_APPLY_MANY: AtomicU64 = AtomicU64::new(0);
static MG_APPLY_ARGS: AtomicU64 = AtomicU64::new(0);
static MG_POST_REDUCE: AtomicU64 = AtomicU64::new(0);
#[inline] fn mg_inc(x: &AtomicU64) { x.fetch_add(1, Ordering::Relaxed); }
pub fn report_iota_cost_stats() {
    if std::env::var_os("MATHGRAPH_IOTA_COST_PROBE").is_none() { return; }
    eprintln!("MATHGRAPH_IOTA_COST fire_calls={} rule_cache_hit={} rule_cache_miss={} apply_many_calls={} apply_args={} post_fire_reduction={} lambda_apply=0 lambda_excess_capture=0 env_extend=0",
        MG_FIRE.load(Ordering::Relaxed), MG_RULE_HIT.load(Ordering::Relaxed), MG_RULE_MISS.load(Ordering::Relaxed),
        MG_APPLY_MANY.load(Ordering::Relaxed), MG_APPLY_ARGS.load(Ordering::Relaxed), MG_POST_REDUCE.load(Ordering::Relaxed));
}
'''
assert anchor in s
s = s.replace(anchor, anchor + probe, 1)

old = '''        let cache_key = (rec_rule.val, levels);\n        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {\n            Some(v) => *v,\n            None => {\n                let v = self.eval_inst(rec_rule.val, rec.info.uparams, levels);\n                self.tc_cache.rec_rule_cache.insert(cache_key, v);\n                v\n            }\n        };'''
new = '''        mg_inc(&MG_FIRE);\n        let cache_key = (rec_rule.val, levels);\n        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {\n            Some(v) => { mg_inc(&MG_RULE_HIT); *v },\n            None => {\n                mg_inc(&MG_RULE_MISS);\n                let v = self.eval_inst(rec_rule.val, rec.info.uparams, levels);\n                self.tc_cache.rec_rule_cache.insert(cache_key, v);\n                v\n            }\n        };'''
assert old in s
s = s.replace(old, new, 1)

old = '''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {\n        let mut f = f0;'''
new = '''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {\n        mg_inc(&MG_APPLY_MANY);\n        MG_APPLY_ARGS.fetch_add(args.len() as u64, Ordering::Relaxed);\n        let mut f = f0;'''
assert old in s
s = s.replace(old, new, 1)

old = '''                ForceStep::Reduced(next) => {\n                    steps += 1;\n                    cur = next;\n                    continue;\n                }'''
new = '''                ForceStep::Reduced(next) => {\n                    if steps > 0 { mg_inc(&MG_POST_REDUCE); }\n                    steps += 1;\n                    cur = next;\n                    continue;\n                }'''
assert old in s
s = s.replace(old, new, 1)

p.write_text(s)

m = root / 'src' / 'main.rs'
t = m.read_text()
anchor2 = '    match out {\n'
repl = '    sokonanoda::eval::report_iota_cost_stats();\n    match out {\n'
assert anchor2 in t
if repl not in t:
    t = t.replace(anchor2, repl, 1)
m.write_text(t)
print('iota cost probe applied')
