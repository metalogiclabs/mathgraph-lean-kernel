#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1])
lib=root/'src/lib.rs'
infer=root/'src/infer.rs'

obs=r'''use crate::value::{Closure, RigidHead, Value, V};
use std::sync::{OnceLock, atomic::{AtomicU64, Ordering}};

static ENABLED: OnceLock<bool> = OnceLock::new();
static EVENT_ID: AtomicU64 = AtomicU64::new(0);
#[inline] fn enabled() -> bool { *ENABLED.get_or_init(|| std::env::var_os("MSI_OBS_TRACE").is_some()) }

#[inline]
pub(crate) fn value_coords(v: V<'_>) -> (u64,u64,u64,u64) {
    let a0 = match v {
        Value::Rigid{..}=>0, Value::Unfold{..}=>1, Value::Lam{..}=>2, Value::Pi{..}=>3,
        Value::Sort{..}=>4, Value::NatLit{..}=>5, Value::StrLit{..}=>6, Value::Thunk{..}=>7,
    };
    let a1 = match v {
        Value::Rigid{head,..} => match head {
            RigidHead::BVar(..)=>0, RigidHead::Axiom(..)=>1, RigidHead::Ctor(..)=>2,
            RigidHead::Recursor(..)=>3, RigidHead::QuotConst(..)=>4, RigidHead::Inductive(..)=>5,
        },
        _ => 0,
    };
    let a2 = u64::from(v.is_canonical());
    let a3 = (v as *const Value<'_> as usize as u64) & 7;
    (a0,a1,a2,a3)
}

#[inline]
pub(crate) fn emit_value(v: V<'_>, q: u8, outcome: u8) {
    if !enabled() { return; }
    let sid = EVENT_ID.fetch_add(1, Ordering::Relaxed);
    let (a0,a1,a2,a3)=value_coords(v);
    eprintln!("MSI_PROD|{sid:x}|{a0}|{a1}|{a2}|{a3}");
    eprintln!("MSI_RES|{sid:x}|q{q}|{outcome}");
}

// A second anonymous object language.  The learner sees only b0..b3.
// b0 and b1 are primitive closure facts; b2/b3 are nuisance coordinates.
#[inline]
pub(crate) fn emit_closure(clo: &Closure<'_>, q: u8) {
    if !enabled() { return; }
    let sid = EVENT_ID.fetch_add(1, Ordering::Relaxed);
    let b0 = u64::from(clo.ctx.is_none());
    let b1 = u64::from(clo.body.num_loose_bvars() == 0);
    let b2 = u64::from(clo.env.len() == 0);
    let b3 = (clo.body.as_ref() as *const _ as usize as u64) & 7;
    let outcome = u8::from(b0 == 1 && b1 == 1);
    eprintln!("MSI_PROD|{sid:x}|{b0}|{b1}|{b2}|{b3}");
    eprintln!("MSI_RES|{sid:x}|q{q}|{outcome}");
}
'''
(root/'src/msi_obs.rs').write_text(obs)

s=lib.read_text()
if 'mod msi_obs;' not in s:
    pos=s.find('\n', s.find('mod ')) if 'mod ' in s else 0
    s=s[:pos+1]+'mod msi_obs;\n'+s[pos+1:]
lib.write_text(s)

s=infer.read_text()
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        crate::msi_obs::emit_value(v, 0, u8::from(matches!(v, Value::Sort { .. })));\n        match self.force_all(depth, v) {'''
assert old in s
s=s.replace(old,new,1)

old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);'''
new='''        while let Some(arg) = args.pop() {\n            crate::msi_obs::emit_value(fty, 1, u8::from(matches!(fty, Value::Pi { .. })));\n            let fty_f = self.force_all(depth, fty);'''
assert old in s
s=s.replace(old,new,1)

old='''            if body.ctx.is_none() && self.ctx.num_loose_bvars(body.body) == 0 {'''
new='''            crate::msi_obs::emit_closure(&body, 3);\n            if body.ctx.is_none() && self.ctx.num_loose_bvars(body.body) == 0 {'''
assert old in s
s=s.replace(old,new,1)
infer.write_text(s)
