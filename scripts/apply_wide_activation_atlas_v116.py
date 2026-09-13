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

const V116_K: usize = 7;
const V116_ROOT: usize = 10;
const V116_MASK: usize = 7;
const V116_CELLS: usize = V116_K * V116_ROOT * V116_MASK;

static V116_CALLS: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_HITS: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_SUCCESS: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_FAIL: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_SELECTED_SUM: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_SAVED_SUM: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];
static V116_SAME_ENV: [AtomicU64; V116_CELLS] = [const { AtomicU64::new(0) }; V116_CELLS];

#[inline]
fn v116_k_bucket(k: u16) -> usize {
    match k {
        0..=96 => 0,
        97..=128 => 1,
        129..=192 => 2,
        193..=256 => 3,
        257..=384 => 4,
        385..=512 => 5,
        _ => 6,
    }
}

#[inline]
fn v116_mask_bucket(n: u32) -> usize {
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
fn v116_root(e: ExprPtr<'_>) -> usize {
    match e.as_ref() {
        Expr::Var { .. } => 0,
        Expr::Sort { .. } => 1,
        Expr::Const { .. } => 2,
        Expr::App { .. } => 3,
        Expr::Pi { .. } => 4,
        Expr::Lambda { .. } => 5,
        Expr::Let { .. } => 6,
        Expr::StringLit { .. } => 7,
        Expr::NatLit { .. } => 8,
        Expr::Proj { .. } => 9,
    }
}

#[inline]
fn v116_cell(e: ExprPtr<'_>, k: u16) -> usize {
    let kb = v116_k_bucket(k);
    let r = v116_root(e);
    let mb = v116_mask_bucket(e.as_ref().fv_mask().count_ones());
    (kb * V116_ROOT + r) * V116_MASK + mb
}

pub fn report_wide_activation_atlas_v116() {
    let roots = ["Var","Sort","Const","App","Pi","Lambda","Let","StringLit","NatLit","Proj"];
    let ks = ["65_96","97_128","129_192","193_256","257_384","385_512","513_plus"];
    let masks = ["0","1_4","5_8","9_16","17_32","33_48","49_64"];
    for kb in 0..V116_K {
        for r in 0..V116_ROOT {
            for mb in 0..V116_MASK {
                let i=(kb*V116_ROOT+r)*V116_MASK+mb;
                let calls=V116_CALLS[i].load(Ordering::Relaxed);
                if calls==0 { continue; }
                eprintln!(
                    "V116_CELL k={} root={} mask={} calls={} hits={} success={} fail={} selected_sum={} saved_sum={} same_env={}",
                    ks[kb], roots[r], masks[mb],
                    calls,
                    V116_HITS[i].load(Ordering::Relaxed),
                    V116_SUCCESS[i].load(Ordering::Relaxed),
                    V116_FAIL[i].load(Ordering::Relaxed),
                    V116_SELECTED_SUM[i].load(Ordering::Relaxed),
                    V116_SAVED_SUM[i].load(Ordering::Relaxed),
                    V116_SAME_ENV[i].load(Ordering::Relaxed),
                );
            }
        }
    }
    eprintln!("V116_COMPLETE=PASS");
}
"""
c=replace_once(c,anchor,insert,"imports")

old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
new="""        if k > 64 {
            let cell = v116_cell(e, k);
            V116_CALLS[cell].fetch_add(1, Ordering::Relaxed);
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                V116_HITS[cell].fetch_add(1, Ordering::Relaxed);
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else {
                V116_FAIL[cell].fetch_add(1, Ordering::Relaxed);
                return env
            };
            V116_SUCCESS[cell].fetch_add(1, Ordering::Relaxed);
            let selected: u64 = words.iter().map(|w| u64::from(w.count_ones())).sum();
            V116_SELECTED_SUM[cell].fetch_add(selected, Ordering::Relaxed);
            let before = u64::from(env.len());
            let r = self.prune_env_wide(env, &words);
            let after = u64::from(r.len());
            V116_SAVED_SUM[cell].fetch_add(before.saturating_sub(after), Ordering::Relaxed);
            if std::ptr::eq(r, env) {
                V116_SAME_ENV[cell].fetch_add(1, Ordering::Relaxed);
            }
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
c=replace_once(c,old,new,"key_env")
p.write_text(c)

p=Path("src/main.rs")
c=p.read_text()
old="    export_file.check_all_declars();\n"
new="""    export_file.check_all_declars();
    if std::env::var_os("MATHGRAPH_V116_ATLAS").is_some() {
        sokonanoda::eval::report_wide_activation_atlas_v116();
    }
"""
c=replace_once(c,old,new,"main report")
p.write_text(c)
print("APPLY_WIDE_ACTIVATION_ATLAS_V116=PASS")
