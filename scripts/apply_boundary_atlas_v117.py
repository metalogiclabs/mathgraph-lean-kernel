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

const V117_K: usize = 7;
const V117_ROOT: usize = 10;
const V117_MASK: usize = 7;
const V117_VM: usize = 8;
const V117_DEPTH: usize = 4;
const V117_SPINE: usize = 5;
const V117_CELLS: usize = V117_K * V117_ROOT * V117_MASK * V117_VM * V117_DEPTH * V117_SPINE;

static V117_CALLS: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_HITS: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_SUCCESS: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_FAIL: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_SELECTED_SUM: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_SAVED_SUM: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];
static V117_SAME_ENV: [AtomicU64; V117_CELLS] = [const { AtomicU64::new(0) }; V117_CELLS];

#[inline]
fn v117_k_bucket(k: u16) -> usize {
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
fn v117_mask_bucket(n: u32) -> usize {
    match n { 0=>0, 1..=4=>1, 5..=8=>2, 9..=16=>3, 17..=32=>4, 33..=48=>5, _=>6 }
}
#[inline]
fn v117_vm_bucket(n: u8) -> usize {
    match n { 0=>0, 1..=4=>1, 5..=8=>2, 9..=16=>3, 17..=32=>4, 33..=64=>5, 65..=128=>6, _=>7 }
}
#[inline]
fn v117_depth_bucket(n: u8) -> usize {
    match n { 0..=3=>0, 4..=7=>1, 8..=11=>2, _=>3 }
}
#[inline]
fn v117_spine_bucket(n: u8) -> usize {
    match n { 0=>0, 1=>1, 2..=3=>2, 4..=7=>3, _=>4 }
}
#[inline]
fn v117_root(e: ExprPtr<'_>) -> usize {
    match e.as_ref() {
        Expr::Var{..}=>0, Expr::Sort{..}=>1, Expr::Const{..}=>2, Expr::App{..}=>3,
        Expr::Pi{..}=>4, Expr::Lambda{..}=>5, Expr::Let{..}=>6,
        Expr::StringLit{..}=>7, Expr::NatLit{..}=>8, Expr::Proj{..}=>9,
    }
}
#[inline]
fn v117_cell(e: ExprPtr<'_>, k: u16) -> usize {
    let kb=v117_k_bucket(k);
    let r=v117_root(e);
    let mb=v117_mask_bucket(e.as_ref().fv_mask().count_ones());
    let vb=v117_vm_bucket(e.as_ref().boundary_var_mass());
    let db=v117_depth_bucket(e.as_ref().boundary_depth());
    let sb=v117_spine_bucket(e.as_ref().boundary_app_spine());
    ((((kb*V117_ROOT+r)*V117_MASK+mb)*V117_VM+vb)*V117_DEPTH+db)*V117_SPINE+sb
}

pub fn report_boundary_atlas_v117() {
    let ks=["65_96","97_128","129_192","193_256","257_384","385_512","513_plus"];
    let roots=["Var","Sort","Const","App","Pi","Lambda","Let","StringLit","NatLit","Proj"];
    let masks=["0","1_4","5_8","9_16","17_32","33_48","49_64"];
    let vms=["0","1_4","5_8","9_16","17_32","33_64","65_128","129_255"];
    let depths=["1_3","4_7","8_11","12_15"];
    let spines=["0","1","2_3","4_7","8_15"];
    for kb in 0..V117_K {
      for r in 0..V117_ROOT {
       for mb in 0..V117_MASK {
        for vb in 0..V117_VM {
         for db in 0..V117_DEPTH {
          for sb in 0..V117_SPINE {
           let i=((((kb*V117_ROOT+r)*V117_MASK+mb)*V117_VM+vb)*V117_DEPTH+db)*V117_SPINE+sb;
           let calls=V117_CALLS[i].load(Ordering::Relaxed);
           if calls==0 { continue; }
           eprintln!(
             "V117_CELL k={} root={} mask={} var_mass={} depth={} app_spine={} calls={} hits={} success={} fail={} selected_sum={} saved_sum={} same_env={}",
             ks[kb],roots[r],masks[mb],vms[vb],depths[db],spines[sb],
             calls,
             V117_HITS[i].load(Ordering::Relaxed),
             V117_SUCCESS[i].load(Ordering::Relaxed),
             V117_FAIL[i].load(Ordering::Relaxed),
             V117_SELECTED_SUM[i].load(Ordering::Relaxed),
             V117_SAVED_SUM[i].load(Ordering::Relaxed),
             V117_SAME_ENV[i].load(Ordering::Relaxed),
           );
          }
         }
        }
       }
      }
    }
    eprintln!("V117_ATLAS_COMPLETE=PASS");
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
            let cell = v117_cell(e, k);
            V117_CALLS[cell].fetch_add(1, Ordering::Relaxed);
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                V117_HITS[cell].fetch_add(1, Ordering::Relaxed);
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else {
                V117_FAIL[cell].fetch_add(1, Ordering::Relaxed);
                return env
            };
            V117_SUCCESS[cell].fetch_add(1, Ordering::Relaxed);
            let selected: u64 = words.iter().map(|w| u64::from(w.count_ones())).sum();
            V117_SELECTED_SUM[cell].fetch_add(selected, Ordering::Relaxed);
            let before = u64::from(env.len());
            let r = self.prune_env_wide(env, &words);
            let after = u64::from(r.len());
            V117_SAVED_SUM[cell].fetch_add(before.saturating_sub(after), Ordering::Relaxed);
            if std::ptr::eq(r, env) {
                V117_SAME_ENV[cell].fetch_add(1, Ordering::Relaxed);
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
    if std::env::var_os("MATHGRAPH_V117_ATLAS").is_some() {
        sokonanoda::eval::report_boundary_atlas_v117();
    }
"""
c=replace_once(c,old,new,"main report")
p.write_text(c)
print("APPLY_BOUNDARY_ATLAS_V117=PASS")
