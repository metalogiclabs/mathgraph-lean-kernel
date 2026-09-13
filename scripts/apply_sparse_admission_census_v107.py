#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

p=Path("src/eval.rs")
c=p.read_text()

anchor="use std::collections::hash_map::Entry;\n"
insert=anchor+"""
use std::sync::atomic::{AtomicU64, Ordering};

static V107_ATTEMPT: [AtomicU64; 7] = [const { AtomicU64::new(0) }; 7];
static V107_ADMIT: [AtomicU64; 7] = [const { AtomicU64::new(0) }; 7];
static V107_ABORT: [AtomicU64; 7] = [const { AtomicU64::new(0) }; 7];
static V107_NODE_CALLS: AtomicU64 = AtomicU64::new(0);
static V107_CACHE_HITS: AtomicU64 = AtomicU64::new(0);
static V107_ADMIT_LEN_SUM: AtomicU64 = AtomicU64::new(0);
static V107_ADMIT_LEN_MAX: AtomicU64 = AtomicU64::new(0);

#[inline]
fn v107_bucket(n: u32) -> usize {
    match n {
        0 => 0,
        1..=4 => 1,
        5..=8 => 2,
        9..=16 => 3,
        17..=32 => 4,
        33..=48 => 5,
        _ => 6,
    }
}

#[inline]
fn v107_record(mask_pop: u32, admitted_len: Option<usize>) {
    let b = v107_bucket(mask_pop);
    V107_ATTEMPT[b].fetch_add(1, Ordering::Relaxed);
    match admitted_len {
        Some(n) => {
            V107_ADMIT[b].fetch_add(1, Ordering::Relaxed);
            V107_ADMIT_LEN_SUM.fetch_add(n as u64, Ordering::Relaxed);
            V107_ADMIT_LEN_MAX.fetch_max(n as u64, Ordering::Relaxed);
        }
        None => { V107_ABORT[b].fetch_add(1, Ordering::Relaxed); }
    }
}

pub fn report_sparse_admission_census() {
    let load = |xs: &[AtomicU64; 7]| -> [u64; 7] {
        std::array::from_fn(|i| xs[i].load(Ordering::Relaxed))
    };
    eprintln!(
        "V107_CENSUS attempts={:?} admits={:?} aborts={:?} node_calls={} cache_hits={} admit_len_sum={} admit_len_max={}",
        load(&V107_ATTEMPT),
        load(&V107_ADMIT),
        load(&V107_ABORT),
        V107_NODE_CALLS.load(Ordering::Relaxed),
        V107_CACHE_HITS.load(Ordering::Relaxed),
        V107_ADMIT_LEN_SUM.load(Ordering::Relaxed),
        V107_ADMIT_LEN_MAX.load(Ordering::Relaxed),
    );
}
"""
c=replace_once(c,anchor,insert,"imports")

old="""    fn exact_sparse_uses_bounded(&mut self, e: ExprPtr<'t>) -> Option<Vec<u16>> {
        if let Some(cached) = self.tc_cache.bounded_sparse_uses_cache.get(&e) {
            return cached.as_ref().map(|x| x.to_vec());
        }"""
new="""    fn exact_sparse_uses_bounded(&mut self, e: ExprPtr<'t>) -> Option<Vec<u16>> {
        V107_NODE_CALLS.fetch_add(1, Ordering::Relaxed);
        if let Some(cached) = self.tc_cache.bounded_sparse_uses_cache.get(&e) {
            V107_CACHE_HITS.fetch_add(1, Ordering::Relaxed);
            return cached.as_ref().map(|x| x.to_vec());
        }"""
c=replace_once(c,old,new,"sparse function entry")

old="""            } else if let Some(indices) = self.exact_sparse_uses_bounded(e) {
                self.prune_env_sparse(env, &indices)
            } else {
                env
            };"""
new="""            } else {
                let sparse = self.exact_sparse_uses_bounded(e);
                v107_record(e.as_ref().fv_mask().count_ones(), sparse.as_ref().map(Vec::len));
                if let Some(indices) = sparse {
                    self.prune_env_sparse(env, &indices)
                } else {
                    env
                }
            };"""
c=replace_once(c,old,new,"key_env decision")
p.write_text(c)

p=Path("src/main.rs")
c=p.read_text()
old="    export_file.check_all_declars();\n"
new="""    export_file.check_all_declars();
    if std::env::var_os("MATHGRAPH_V107_CENSUS").is_some() {
        sokonanoda::eval::report_sparse_admission_census();
    }
"""
c=replace_once(c,old,new,"main report")
p.write_text(c)

print("APPLY_SPARSE_ADMISSION_CENSUS_V107=PASS")
