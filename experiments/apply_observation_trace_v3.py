#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1])
lib=root/'src/lib.rs'
infer=root/'src/infer.rs'

obs=r'''use crate::value::{RigidHead, Value, V};
use std::sync::OnceLock;

static ENABLED: OnceLock<bool> = OnceLock::new();
#[inline] fn enabled() -> bool { *ENABLED.get_or_init(|| std::env::var_os("MSI_OBS_TRACE").is_some()) }

// Frozen mechanically enumerable producer-coordinate grammar.  The trace
// consumer receives only a0..a3 values; semantic names are not emitted.
#[inline]
pub(crate) fn coords(v: V<'_>) -> (u64,u64,u64,u64) {
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
pub(crate) fn emit(v: V<'_>, q: u8, outcome: u8) {
    if !enabled() { return; }
    let sid=v as *const Value<'_> as usize;
    let (a0,a1,a2,a3)=coords(v);
    eprintln!("MSI_PROD|{sid:x}|{a0}|{a1}|{a2}|{a3}");
    eprintln!("MSI_RES|{sid:x}|q{q}|{outcome}");
}
'''
(root/'src/msi_obs.rs').write_text(obs)

s=lib.read_text()
if 'mod msi_obs;' not in s:
    marker='mod'
    # Module order is not semantically relevant. Put near the top after attrs/comments.
    pos=s.find('\n', s.find('mod ')) if 'mod ' in s else 0
    s=s[:pos+1]+'mod msi_obs;\n'+s[pos+1:]
lib.write_text(s)

s=infer.read_text()
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        crate::msi_obs::emit(v, 0, u8::from(matches!(v, Value::Sort { .. })));\n        match self.force_all(depth, v) {'''
assert old in s
s=s.replace(old,new,1)
old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);'''
new='''        while let Some(arg) = args.pop() {\n            crate::msi_obs::emit(fty, 1, u8::from(matches!(fty, Value::Pi { .. })));\n            let fty_f = self.force_all(depth, fty);'''
assert old in s
s=s.replace(old,new,1)
infer.write_text(s)
