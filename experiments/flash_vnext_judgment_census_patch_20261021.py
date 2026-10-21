#!/usr/bin/env python3
"""Instrument actual type/eval overlap at the unified open contextual cache.

Diagnostic only, enabled by Cargo feature judgment-census; production builds
never compile the counters. Tracks visits after the source key_env projection,
and distinguishes typed from checked-under-current-authority.
"""
from pathlib import Path
import sys
if len(sys.argv)!=2:raise SystemExit("usage: patch.py CHECKER_TREE")
root=Path(sys.argv[1])

def one(s, old, new, label):
    assert s.count(old)==1, (label,s.count(old))
    return s.replace(old,new)

p=root/"Cargo.toml"
s=p.read_text()
s=one(s,"top-byte-ignore = []","top-byte-ignore = []\njudgment-census = []","feature")
p.write_text(s)

p=root/"src/checker/cache.rs"
s=p.read_text()
assert "FLASH_JUDGMENT_CENSUS" not in s, "diagnostic already instrumented"
s += r'''
// This diagnostic is excluded entirely from normal checker builds.
#[cfg(feature = "judgment-census")]
mod joint_census {
    use std::cell::Cell;

    pub(super) struct Counters {
        type_calls: Cell<u64>,
        type_hits: Cell<u64>,
        type_with_value: Cell<u64>,
        type_miss_with_value: Cell<u64>,
        eval_calls: Cell<u64>,
        eval_hits: Cell<u64>,
        eval_with_type: Cell<u64>,
        eval_with_checked_type: Cell<u64>,
        eval_miss_with_type: Cell<u64>,
    }

    impl Counters {
        const fn new() -> Self {
            Self {
                type_calls: Cell::new(0),
                type_hits: Cell::new(0),
                type_with_value: Cell::new(0),
                type_miss_with_value: Cell::new(0),
                eval_calls: Cell::new(0),
                eval_hits: Cell::new(0),
                eval_with_type: Cell::new(0),
                eval_with_checked_type: Cell::new(0),
                eval_miss_with_type: Cell::new(0),
            }
        }

        #[inline]
        fn bump(x: &Cell<u64>) { x.set(x.get() + 1); }

        fn type_lookup(&self, hit: bool, with_value: bool) {
            Self::bump(&self.type_calls);
            if hit { Self::bump(&self.type_hits); }
            if with_value {
                Self::bump(&self.type_with_value);
                if !hit { Self::bump(&self.type_miss_with_value); }
            }
        }

        fn eval_lookup(&self, hit: bool, with_type: bool, with_checked_type: bool) {
            Self::bump(&self.eval_calls);
            if hit { Self::bump(&self.eval_hits); }
            if with_type {
                Self::bump(&self.eval_with_type);
                if with_checked_type { Self::bump(&self.eval_with_checked_type); }
                if !hit { Self::bump(&self.eval_miss_with_type); }
            }
        }
    }

    impl Drop for Counters {
        fn drop(&mut self) {
            // One JSON record per checker worker at thread exit.
            eprintln!(
                "FLASH_JUDGMENT_CENSUS={{\"type_calls\":{},\"type_hits\":{},\"type_with_value\":{},\"type_miss_with_value\":{},\"eval_calls\":{},\"eval_hits\":{},\"eval_with_type\":{},\"eval_with_checked_type\":{},\"eval_miss_with_type\":{}}}",
                self.type_calls.get(), self.type_hits.get(),
                self.type_with_value.get(), self.type_miss_with_value.get(),
                self.eval_calls.get(), self.eval_hits.get(),
                self.eval_with_type.get(), self.eval_with_checked_type.get(),
                self.eval_miss_with_type.get()
            );
        }
    }

    thread_local! {
        static COUNTERS: Counters = const { Counters::new() };
    }

    pub(crate) fn type_lookup(hit: bool, with_value: bool) {
        COUNTERS.with(|c| c.type_lookup(hit, with_value));
    }

    pub(crate) fn eval_lookup(hit: bool, with_type: bool, with_checked_type: bool) {
        COUNTERS.with(|c| c.eval_lookup(hit, with_type, with_checked_type));
    }
}

#[cfg(feature = "judgment-census")]
pub(crate) use joint_census::{eval_lookup as census_eval_lookup, type_lookup as census_type_lookup};
'''
p.write_text(s)

p=root/"src/checker/infer.rs"
s=p.read_text()
needle="        let scope = self.uparam_scope();\n"
replacement="""        let scope = self.uparam_scope();
        #[cfg(feature = "judgment-census")]
        {
            let record = self.tc_cache.judgment_cache.get(&key);
            let has_value = record.is_some_and(|j| j.value.is_some());
            let valid_type = record.and_then(|j| j.checked_type).is_some_and(
                |t| flag == InferOnly || t.checked_under == scope
            );
            crate::checker::cache::census_type_lookup(valid_type, has_value);
        }
"""
s=one(s,needle,replacement,"infer record census")
p.write_text(s)

p=root/"src/checker/eval.rs"
s=p.read_text()
needle="""            let key = (Id::of(te), e);
            if let Some(judgment) = self.tc_cache.judgment_cache.get(&key)"""
replacement="""            let key = (Id::of(te), e);
            #[cfg(feature = "judgment-census")]
            {
                use crate::checker::infer::CheckScope;
                let record = self.tc_cache.judgment_cache.get(&key);
                let has_checked_type = record.and_then(|j| j.checked_type)
                    .is_some_and(|t| t.checked_under != CheckScope::Unchecked);
                crate::checker::cache::census_eval_lookup(
                    record.is_some_and(|j| j.value.is_some()),
                    record.is_some_and(|j| j.checked_type.is_some()),
                    has_checked_type,
                );
            }
            if let Some(judgment) = self.tc_cache.judgment_cache.get(&key)"""
s=one(s,needle,replacement,"eval record census")
p.write_text(s)
print("FLASH_VNEXT_JUDGMENT_CENSUS=INSTRUMENTED_ONLY_WHEN_FEATURE_ENABLED",flush=True)
