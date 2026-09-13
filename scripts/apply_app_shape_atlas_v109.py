#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

p=Path("src/eval.rs")
c=p.read_text()

anchor="""static V108_ABORT: [AtomicU64; V108_CELLS] = [const { AtomicU64::new(0) }; V108_CELLS];
"""
insert=anchor+"""
const V109_ROOTS: usize = 10;
const V109_MASKS: usize = 7;
const V109_CELLS: usize = V109_ROOTS * V109_ROOTS * V109_MASKS * V109_MASKS;
static V109_ADMIT: [AtomicU64; V109_CELLS] = [const { AtomicU64::new(0) }; V109_CELLS];
static V109_ABORT: [AtomicU64; V109_CELLS] = [const { AtomicU64::new(0) }; V109_CELLS];

#[inline]
fn v109_record(e: ExprPtr<'_>, admitted: bool) {
    let Expr::App { fun, arg, .. } = e.as_ref() else { return };
    let fr = v108_root(*fun);
    let ar = v108_root(*arg);
    let fm = v107_bucket(fun.as_ref().fv_mask().count_ones());
    let am = v107_bucket(arg.as_ref().fv_mask().count_ones());
    let i = (((fr * V109_ROOTS) + ar) * V109_MASKS + fm) * V109_MASKS + am;
    if admitted {
        V109_ADMIT[i].fetch_add(1, Ordering::Relaxed);
    } else {
        V109_ABORT[i].fetch_add(1, Ordering::Relaxed);
    }
}

fn report_app_shape_atlas() {
    const ROOT_NAMES: [&str; V109_ROOTS] =
        ["Var","Sort","Const","App","Pi","Lambda","Let","StringLit","NatLit","Proj"];
    const MASK_NAMES: [&str; V109_MASKS] =
        ["0","1_4","5_8","9_16","17_32","33_48","49_64"];
    for fr in 0..V109_ROOTS {
        for ar in 0..V109_ROOTS {
            for fm in 0..V109_MASKS {
                for am in 0..V109_MASKS {
                    let i = (((fr * V109_ROOTS) + ar) * V109_MASKS + fm) * V109_MASKS + am;
                    let a = V109_ADMIT[i].load(Ordering::Relaxed);
                    let b = V109_ABORT[i].load(Ordering::Relaxed);
                    if a != 0 || b != 0 {
                        eprintln!(
                            "V109_CELL fun_root={} arg_root={} fun_mask={} arg_mask={} admit={} abort={}",
                            ROOT_NAMES[fr], ROOT_NAMES[ar], MASK_NAMES[fm], MASK_NAMES[am], a, b
                        );
                    }
                }
            }
        }
    }
}
"""
c=replace_once(c,anchor,insert,"v109 statics")

old="""                v108_record(e, k, sparse.is_some());
                if let Some(indices) = sparse {"""
new="""                v108_record(e, k, sparse.is_some());
                v109_record(e, sparse.is_some());
                if let Some(indices) = sparse {"""
c=replace_once(c,old,new,"v109 record")

old="""    report_sparse_feature_atlas();
}"""
new="""    report_sparse_feature_atlas();
    report_app_shape_atlas();
}"""
c=replace_once(c,old,new,"v109 report")
p.write_text(c)

print("APPLY_APP_SHAPE_ATLAS_V109=PASS")
