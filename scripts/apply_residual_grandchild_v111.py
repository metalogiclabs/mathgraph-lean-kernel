#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old, new, 1)

p = Path("src/eval.rs")
c = p.read_text()

anchor = """fn report_app_shape_atlas() {
"""
insert = """#[inline]
fn v111_app_children(e: ExprPtr<'_>) -> (usize, usize, usize, usize) {
    if let Expr::App { fun, arg, .. } = e.as_ref() {
        (
            v108_root(*fun),
            v108_root(*arg),
            v107_bucket(fun.as_ref().fv_mask().count_ones()),
            v107_bucket(arg.as_ref().fv_mask().count_ones()),
        )
    } else {
        (10, 10, 7, 7)
    }
}

#[inline]
fn v111_record(e: ExprPtr<'_>, admitted: bool) {
    let Expr::App { fun, arg, .. } = e.as_ref() else { return };
    let fr = v108_root(*fun);
    let ar = v108_root(*arg);
    let fm = v107_bucket(fun.as_ref().fv_mask().count_ones());
    let am = v107_bucket(arg.as_ref().fv_mask().count_ones());

    // Residual cells are generated mechanically by V110.
    let residual =
        (fr == 3 && ar == 3 && fm == 0 && am == 0)
        || (fr == 3 && ar == 3 && fm == 1 && am == 0)
        || (fr == 3 && ar == 0 && fm == 0 && am == 0)
        || (fr == 3 && ar == 0 && fm == 0 && am == 1);
    if !residual {
        return;
    }

    let (ffr, far, ffm, fam) = v111_app_children(*fun);
    let (afr, aar, afm, aam) = v111_app_children(*arg);
    eprintln!(
        "V111_EVENT fr={} ar={} fm={} am={} ffr={} far={} ffm={} fam={} afr={} aar={} afm={} aam={} admit={}",
        fr, ar, fm, am, ffr, far, ffm, fam, afr, aar, afm, aam, if admitted { 1 } else { 0 }
    );
}

""" + anchor
c = replace_once(c, anchor, insert, "v111 helpers")

old = """                v109_record(e, sparse.is_some());
                if let Some(indices) = sparse {"""
new = """                v109_record(e, sparse.is_some());
                v111_record(e, sparse.is_some());
                if let Some(indices) = sparse {"""
c = replace_once(c, old, new, "v111 record")

p.write_text(c)
print("APPLY_RESIDUAL_GRANDCHILD_ATLAS_V111=PASS")
