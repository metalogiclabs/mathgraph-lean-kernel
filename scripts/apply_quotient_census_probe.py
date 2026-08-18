#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'eval.rs'
s = p.read_text()

anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_FORCE_CENSUS_SEQ: AtomicU64 = AtomicU64::new(0);

#[inline]
fn mg_census_on() -> bool { std::env::var_os("MATHGRAPH_QUOTIENT_CENSUS").is_some() }
'''
if insert not in s:
    assert anchor in s
    s = s.replace(anchor, anchor + insert, 1)

old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {'''
new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if mg_census_on() {\n            let n = MG_FORCE_CENSUS_SEQ.fetch_add(1, Ordering::Relaxed);\n            if n & 1023 == 0 {\n                match v {\n                    Value::Pi { body, .. } => eprintln!("MG_FORCE_SAMPLE kind=pi depth={} exact={} body={} env={} closed={}", depth, v as *const Value<'t> as usize, body.body.as_ref() as *const Expr<'t> as usize, body.env as *const value::Env<'t> as usize, v.is_closed() as u8),\n                    Value::Lam { body, .. } => eprintln!("MG_FORCE_SAMPLE kind=lam depth={} exact={} body={} env={} closed={}", depth, v as *const Value<'t> as usize, body.body.as_ref() as *const Expr<'t> as usize, body.env as *const value::Env<'t> as usize, v.is_closed() as u8),\n                    Value::Rigid { head, spine, .. } => { let (k,a,b)=rigid_head_key(head); eprintln!("MG_FORCE_SAMPLE kind=rigid depth={} exact={} hk={} ha={} hb={} spine_len={} closed={}", depth, v as *const Value<'t> as usize, k,a,b,spine.len(),v.is_closed() as u8); },\n                    Value::Unfold { head, spine, .. } => eprintln!("MG_FORCE_SAMPLE kind=unfold depth={} exact={} name={} levels={} spine_len={} closed={}", depth, v as *const Value<'t> as usize, head.name.get_hash(), head.levels.get_hash(), spine.len(), v.is_closed() as u8),\n                    Value::Thunk { expr, env, .. } => eprintln!("MG_FORCE_SAMPLE kind=thunk depth={} exact={} expr={} env={} closed={}", depth, v as *const Value<'t> as usize, expr.as_ref() as *const Expr<'t> as usize, *env as *const value::Env<'t> as usize, v.is_closed() as u8),\n                    Value::Sort { .. } => eprintln!("MG_FORCE_SAMPLE kind=sort depth={} exact={} closed={}", depth, v as *const Value<'t> as usize, v.is_closed() as u8),\n                    Value::NatLit { .. } => eprintln!("MG_FORCE_SAMPLE kind=nat depth={} exact={} closed={}", depth, v as *const Value<'t> as usize, v.is_closed() as u8),\n                    Value::StrLit { .. } => eprintln!("MG_FORCE_SAMPLE kind=str depth={} exact={} closed={}", depth, v as *const Value<'t> as usize, v.is_closed() as u8),\n                }\n            }\n        }\n        if let Some(r) = self.store_lookup(depth, v) {'''
assert old in s
s = s.replace(old, new, 1)

old = '''        let rec_rule = rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?;\n        let num_extra = ctor_args.len().checked_sub(usize::from(rec_rule.ctor_telescope_size_wo_params))?;'''
new = '''        let rec_rule = rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?;\n        let num_extra = ctor_args.len().checked_sub(usize::from(rec_rule.ctor_telescope_size_wo_params))?;\n        if mg_census_on() {\n            let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);\n            eprintln!("MG_IOTA_FIRE rec={} ctor={} rule={} ctor_args={} extra={} prefix={} tail={} major_idx={} depth={}",\n                rec.info.name.get_hash(), ctor_name.get_hash(), rec_rule.val.as_ref() as *const Expr<'t> as usize,\n                ctor_args.len(), num_extra, nprefix, args.len().saturating_sub(rec.major_idx()+1), rec.major_idx(), depth);\n        }'''
assert old in s
s = s.replace(old, new, 1)

p.write_text(s)
print('quotient census probe applied')
