#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

# eval.rs instrumentation
p=Path("src/eval.rs")
c=p.read_text()
anchor="use std::collections::hash_map::Entry;\n"
insert=anchor+"""
use std::sync::atomic::{AtomicU64, Ordering};

static DEEP_KEY_CALLS: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_0: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_1_4: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_5_8: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_9_16: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_17_32: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_33_48: AtomicU64 = AtomicU64::new(0);
static DEEP_MASK_49_64: AtomicU64 = AtomicU64::new(0);

#[inline]
fn census_deep_mask(mask: u64) {
    DEEP_KEY_CALLS.fetch_add(1, Ordering::Relaxed);
    match mask.count_ones() {
        0 => { DEEP_MASK_0.fetch_add(1, Ordering::Relaxed); }
        1..=4 => { DEEP_MASK_1_4.fetch_add(1, Ordering::Relaxed); }
        5..=8 => { DEEP_MASK_5_8.fetch_add(1, Ordering::Relaxed); }
        9..=16 => { DEEP_MASK_9_16.fetch_add(1, Ordering::Relaxed); }
        17..=32 => { DEEP_MASK_17_32.fetch_add(1, Ordering::Relaxed); }
        33..=48 => { DEEP_MASK_33_48.fetch_add(1, Ordering::Relaxed); }
        _ => { DEEP_MASK_49_64.fetch_add(1, Ordering::Relaxed); }
    }
}

pub fn report_deep_relevance_census() {
    eprintln!(
        "V106_CENSUS deep_calls={} mask0={} mask1_4={} mask5_8={} mask9_16={} mask17_32={} mask33_48={} mask49_64={}",
        DEEP_KEY_CALLS.load(Ordering::Relaxed),
        DEEP_MASK_0.load(Ordering::Relaxed),
        DEEP_MASK_1_4.load(Ordering::Relaxed),
        DEEP_MASK_5_8.load(Ordering::Relaxed),
        DEEP_MASK_9_16.load(Ordering::Relaxed),
        DEEP_MASK_17_32.load(Ordering::Relaxed),
        DEEP_MASK_33_48.load(Ordering::Relaxed),
        DEEP_MASK_49_64.load(Ordering::Relaxed),
    );
}
"""
c=replace_once(c,anchor,insert,"eval imports")

old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);"""
new="""        if k > 64 {
            if k > 512 {
                census_deep_mask(e.as_ref().fv_mask());
            }
            let ck = (env as *const value::Env<'t> as usize, e);"""
c=replace_once(c,old,new,"key_env census")
p.write_text(c)

# main.rs report at end of use_config after checking
p=Path("src/main.rs")
c=p.read_text()
old="    export_file.check_all_declars();\n"
new="""    export_file.check_all_declars();
    if std::env::var_os("MATHGRAPH_DEEP_CENSUS").is_some() {
        sokonanoda::eval::report_deep_relevance_census();
    }
"""
c=replace_once(c,old,new,"main report")
p.write_text(c)

print("APPLY_DEEP_RELEVANCE_CENSUS_V106=PASS")
