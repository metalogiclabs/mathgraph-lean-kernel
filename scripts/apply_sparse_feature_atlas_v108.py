#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

p=Path("src/eval.rs")
c=p.read_text()

anchor="""static V107_ADMIT_LEN_MAX: AtomicU64 = AtomicU64::new(0);
"""
insert=anchor+"""
const V108_ROOTS: usize = 10;
const V108_MASKS: usize = 7;
const V108_DEPTHS: usize = 7;
const V108_CELLS: usize = V108_ROOTS * V108_MASKS * V108_DEPTHS;
static V108_ADMIT: [AtomicU64; V108_CELLS] = [const { AtomicU64::new(0) }; V108_CELLS];
static V108_ABORT: [AtomicU64; V108_CELLS] = [const { AtomicU64::new(0) }; V108_CELLS];

#[inline]
fn v108_root(e: ExprPtr<'_>) -> usize {
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
fn v108_depth(k: u16) -> usize {
    match k {
        0..=768 => 0,
        769..=1024 => 1,
        1025..=1536 => 2,
        1537..=2048 => 3,
        2049..=3072 => 4,
        3073..=4096 => 5,
        _ => 6,
    }
}

#[inline]
fn v108_record(e: ExprPtr<'_>, k: u16, admitted: bool) {
    let r = v108_root(e);
    let m = v107_bucket(e.as_ref().fv_mask().count_ones());
    let d = v108_depth(k);
    let i = (r * V108_MASKS + m) * V108_DEPTHS + d;
    if admitted {
        V108_ADMIT[i].fetch_add(1, Ordering::Relaxed);
    } else {
        V108_ABORT[i].fetch_add(1, Ordering::Relaxed);
    }
}

fn report_sparse_feature_atlas() {
    const ROOT_NAMES: [&str; V108_ROOTS] =
        ["Var","Sort","Const","App","Pi","Lambda","Let","StringLit","NatLit","Proj"];
    const MASK_NAMES: [&str; V108_MASKS] =
        ["0","1_4","5_8","9_16","17_32","33_48","49_64"];
    const DEPTH_NAMES: [&str; V108_DEPTHS] =
        ["513_768","769_1024","1025_1536","1537_2048","2049_3072","3073_4096","4097_plus"];
    for r in 0..V108_ROOTS {
        for m in 0..V108_MASKS {
            for d in 0..V108_DEPTHS {
                let i = (r * V108_MASKS + m) * V108_DEPTHS + d;
                let a = V108_ADMIT[i].load(Ordering::Relaxed);
                let b = V108_ABORT[i].load(Ordering::Relaxed);
                if a != 0 || b != 0 {
                    eprintln!(
                        "V108_CELL root={} mask={} depth={} admit={} abort={}",
                        ROOT_NAMES[r], MASK_NAMES[m], DEPTH_NAMES[d], a, b
                    );
                }
            }
        }
    }
}
"""
c=replace_once(c,anchor,insert,"v108 statics")

old="""                v107_record(e.as_ref().fv_mask().count_ones(), sparse.as_ref().map(Vec::len));
                if let Some(indices) = sparse {"""
new="""                v107_record(e.as_ref().fv_mask().count_ones(), sparse.as_ref().map(Vec::len));
                v108_record(e, k, sparse.is_some());
                if let Some(indices) = sparse {"""
c=replace_once(c,old,new,"v108 record")

old="""        V107_ADMIT_LEN_MAX.load(Ordering::Relaxed),
    );
}"""
new="""        V107_ADMIT_LEN_MAX.load(Ordering::Relaxed),
    );
    report_sparse_feature_atlas();
}"""
c=replace_once(c,old,new,"v108 report")
p.write_text(c)

print("APPLY_SPARSE_FEATURE_ATLAS_V108=PASS")
