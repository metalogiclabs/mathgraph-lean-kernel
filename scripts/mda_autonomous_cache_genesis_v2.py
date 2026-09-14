#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, statistics
from pathlib import Path

ROOTS=["App","Proj","Let","Pi","Lambda"]
MASKS=["0","1_4","5_8","9_16","17_32","33_64"]
DEPTHS=["0","1_2","3_7","8_plus"]
CHILDREN=["Var","Sort","Const","App","Pi","Lambda","Let","Proj","NatLit","StringLit","NONE"]
BASE_CELLS=len(ROOTS)*len(MASKS)*len(DEPTHS)
SHAPES=len(CHILDREN)**3
NCELLS=BASE_CELLS*SHAPES

OPEN_OLD="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }
"""

FEATURE_HELPER=r"""
const MDA_V2_OPEN_ROOTS: usize = 5;
const MDA_V2_OPEN_MASKS: usize = 6;
const MDA_V2_OPEN_DEPTHS: usize = 4;
const MDA_V2_CHILD_KINDS: usize = 11;
const MDA_V2_BASE_CELLS: usize = MDA_V2_OPEN_ROOTS * MDA_V2_OPEN_MASKS * MDA_V2_OPEN_DEPTHS;
const MDA_V2_SHAPES: usize = MDA_V2_CHILD_KINDS * MDA_V2_CHILD_KINDS * MDA_V2_CHILD_KINDS;
const MDA_V2_CELLS: usize = MDA_V2_BASE_CELLS * MDA_V2_SHAPES;
const MDA_V2_NONE: usize = 10;

#[inline]
fn mda_v2_expr_kind(e: ExprPtr<'_>) -> usize {
    match e.as_ref() {
        Expr::Var { .. } => 0,
        Expr::Sort { .. } => 1,
        Expr::Const { .. } => 2,
        Expr::App { .. } => 3,
        Expr::Pi { .. } => 4,
        Expr::Lambda { .. } => 5,
        Expr::Let { .. } => 6,
        Expr::Proj { .. } => 7,
        Expr::NatLit { .. } => 8,
        Expr::StringLit { .. } => 9,
    }
}

#[inline]
fn mda_v2_open_root(e: ExprPtr<'_>) -> Option<usize> {
    match e.as_ref() {
        Expr::App { .. } => Some(0),
        Expr::Proj { .. } => Some(1),
        Expr::Let { .. } => Some(2),
        Expr::Pi { .. } => Some(3),
        Expr::Lambda { .. } => Some(4),
        _ => None,
    }
}

#[inline]
fn mda_v2_open_mask(e: ExprPtr<'_>) -> usize {
    match e.as_ref().fv_mask().count_ones() {
        0 => 0,
        1..=4 => 1,
        5..=8 => 2,
        9..=16 => 3,
        17..=32 => 4,
        _ => 5,
    }
}

#[inline]
fn mda_v2_open_depth(depth: u32) -> usize {
    match depth {
        0 => 0,
        1..=2 => 1,
        3..=7 => 2,
        _ => 3,
    }
}

#[inline]
fn mda_v2_child_shape(e: ExprPtr<'_>) -> (usize, usize, usize) {
    match e.as_ref() {
        Expr::App { fun, arg, .. } =>
            (mda_v2_expr_kind(*fun), mda_v2_expr_kind(*arg), MDA_V2_NONE),
        Expr::Proj { structure, .. } =>
            (mda_v2_expr_kind(*structure), MDA_V2_NONE, MDA_V2_NONE),
        Expr::Pi { binder_type, body, .. } | Expr::Lambda { binder_type, body, .. } =>
            (mda_v2_expr_kind(*binder_type), mda_v2_expr_kind(*body), MDA_V2_NONE),
        Expr::Let { data, .. } =>
            (mda_v2_expr_kind(data.binder_type), mda_v2_expr_kind(data.val), mda_v2_expr_kind(data.body)),
        _ => (MDA_V2_NONE, MDA_V2_NONE, MDA_V2_NONE),
    }
}

#[inline]
fn mda_v2_open_cell(e: ExprPtr<'_>, depth: u32) -> Option<usize> {
    let r = mda_v2_open_root(e)?;
    let base = (r * MDA_V2_OPEN_MASKS + mda_v2_open_mask(e)) * MDA_V2_OPEN_DEPTHS
        + mda_v2_open_depth(depth);
    let (a,b,c) = mda_v2_child_shape(e);
    let shape = (a * MDA_V2_CHILD_KINDS + b) * MDA_V2_CHILD_KINDS + c;
    Some(base * MDA_V2_SHAPES + shape)
}
"""

CENSUS_EXTRA=r"""
static MDA_V2_HITS: [AtomicU64; MDA_V2_CELLS] =
    [const { AtomicU64::new(0) }; MDA_V2_CELLS];
static MDA_V2_MISSES: [AtomicU64; MDA_V2_CELLS] =
    [const { AtomicU64::new(0) }; MDA_V2_CELLS];

pub fn mda_v2_report_open_cache_census() {
    if std::env::var_os("MDA_V2_CACHE_CENSUS").is_none() {
        return;
    }
    const ROOT_NAMES: [&str; MDA_V2_OPEN_ROOTS] = ["App","Proj","Let","Pi","Lambda"];
    const MASK_NAMES: [&str; MDA_V2_OPEN_MASKS] = ["0","1_4","5_8","9_16","17_32","33_64"];
    const DEPTH_NAMES: [&str; MDA_V2_OPEN_DEPTHS] = ["0","1_2","3_7","8_plus"];
    const CHILD_NAMES: [&str; MDA_V2_CHILD_KINDS] =
        ["Var","Sort","Const","App","Pi","Lambda","Let","Proj","NatLit","StringLit","NONE"];

    for key in 0..MDA_V2_CELLS {
        let h = MDA_V2_HITS[key].load(Ordering::Relaxed);
        let m = MDA_V2_MISSES[key].load(Ordering::Relaxed);
        if h == 0 && m == 0 {
            continue;
        }
        let base = key / MDA_V2_SHAPES;
        let mut shape = key % MDA_V2_SHAPES;
        let c3 = shape % MDA_V2_CHILD_KINDS;
        shape /= MDA_V2_CHILD_KINDS;
        let c2 = shape % MDA_V2_CHILD_KINDS;
        let c1 = shape / MDA_V2_CHILD_KINDS;
        let d = base % MDA_V2_OPEN_DEPTHS;
        let rm = base / MDA_V2_OPEN_DEPTHS;
        let mb = rm % MDA_V2_OPEN_MASKS;
        let r = rm / MDA_V2_OPEN_MASKS;
        eprintln!(
            "MDA_V2_CACHE_CELL key={} root={} mask={} depth={} c1={} c2={} c3={} hits={} misses={}",
            key, ROOT_NAMES[r], MASK_NAMES[mb], DEPTH_NAMES[d],
            CHILD_NAMES[c1], CHILD_NAMES[c2], CHILD_NAMES[c3], h, m
        );
    }
}
"""

CENSUS_OPEN=r"""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            let cell = mda_v2_open_cell(e, depth);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                if let Some(i) = cell {
                    MDA_V2_HITS[i].fetch_add(1, Ordering::Relaxed);
                }
                return v;
            }
            if let Some(i) = cell {
                MDA_V2_MISSES[i].fetch_add(1, Ordering::Relaxed);
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }
"""

CELL_RE=re.compile(
    r"MDA_V2_CACHE_CELL key=(\d+) root=(\S+) mask=(\S+) depth=(\S+) "
    r"c1=(\S+) c2=(\S+) c3=(\S+) hits=(\d+) misses=(\d+)"
)

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

def add_feature_helper(c):
    anchor="const FAIL_DEPTH: u8 = 7;\n"
    return replace_once(c,anchor,anchor+"\n"+FEATURE_HELPER,"feature helper")

def instrument(eval_path:Path, main_path:Path):
    c=eval_path.read_text()
    c=replace_once(
        c,"use std::cell::OnceCell;\n",
        "use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};\n",
        "atomic import")
    c=add_feature_helper(c)
    c=replace_once(c,FEATURE_HELPER,FEATURE_HELPER+"\n"+CENSUS_EXTRA,"census statics")
    c=replace_once(c,OPEN_OLD,CENSUS_OPEN,"open eval census")
    eval_path.write_text(c)

    m=main_path.read_text()
    m=replace_once(
        m,"    export_file.check_all_declars();\n",
        "    export_file.check_all_declars();\n    sokonanoda::eval::mda_v2_report_open_cache_census();\n",
        "main census report")
    main_path.write_text(m)

def parse_census(paths, out):
    by={}
    for pstr in paths:
        p=Path(pstr)
        for line in p.read_text(errors="replace").splitlines():
            m=CELL_RE.search(line)
            if not m:
                continue
            key,root,mask,depth,c1,c2,c3,hits,misses=m.groups()
            key=int(key)
            r=by.setdefault(key,{"key":key,"root":root,"mask":mask,"depth":depth,
                                 "c1":c1,"c2":c2,"c3":c3,"hits":0,"misses":0})
            assert (r["root"],r["mask"],r["depth"],r["c1"],r["c2"],r["c3"]) == (root,mask,depth,c1,c2,c3)
            r["hits"]+=int(hits); r["misses"]+=int(misses)
    rows=[]
    for key in sorted(by):
        r=by[key]
        total=r["hits"]+r["misses"]
        r["events"]=total
        r["hit_ratio"]=r["hits"]/total if total else 0.0
        rows.append(r)
    payload={
        "schema":"mda-autonomous-cache-census-v2",
        "full_cell_universe":NCELLS,
        "observed_cells":len(rows),
        "cells":rows,
        "totals":{"hits":sum(r["hits"] for r in rows),"misses":sum(r["misses"] for r in rows)}
    }
    Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(f"MDA_V2_CENSUS observed={len(rows)} hits={payload['totals']['hits']} misses={payload['totals']['misses']}")

def make_policies(census_path,outdir):
    d=json.loads(Path(census_path).read_text())
    cells=d["cells"]
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    hs=[1,2,4,8,16]
    rs=[0.0,0.01,0.05,0.10,0.20,0.40]
    all_labels=[]; unique_labels=[]; seen={}
    for h in hs:
        for ratio in rs:
            override=tuple(sorted(
                c["key"] for c in cells
                if not (c["hits"]>=h and c["hit_ratio"]>=ratio)
            ))
            label=f"h{h}_r{str(ratio).replace('.','p')}"
            behavior=(True,override)
            rep=seen.get(behavior)
            payload={
                "schema":"mda-cache-policy-v2","label":label,"h":h,"r":ratio,
                "default_admit":True,"override_keys":list(override),
                "observed_cells":len(cells),"bypassed_observed_cells":len(override),
                "behavioral_representative":rep or label,
                "source":"training_census_only"
            }
            (out/f"{label}.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
            all_labels.append(label)
            if rep is None:
                seen[behavior]=label
                unique_labels.append(label)
    neg={
        "schema":"mda-cache-policy-v2","label":"all_bypass","h":None,"r":None,
        "default_admit":False,"override_keys":[],"observed_cells":len(cells),
        "bypassed_observed_cells":len(cells),"behavioral_representative":"all_bypass",
        "source":"negative_control"
    }
    (out/"all_bypass.json").write_text(json.dumps(neg,indent=2,sort_keys=True)+"\n")
    (out/"labels.txt").write_text("\n".join(unique_labels+["all_bypass"])+"\n")
    (out/"all-threshold-labels.txt").write_text("\n".join(all_labels)+"\n")
    print(f"MDA_V2_POLICY_THRESHOLDS={len(all_labels)} UNIQUE_BEHAVIORS={len(unique_labels)}")

def apply_policy(clean_eval:Path, policy_path:Path, dest:Path):
    c=clean_eval.read_text()
    p=json.loads(policy_path.read_text())
    c=add_feature_helper(c)
    default="true" if p["default_admit"] else "false"
    keys=", ".join(str(int(x)) for x in p["override_keys"])
    policy_src=f"""
const MDA_V2_DEFAULT_ADMIT: bool = {default};
const MDA_V2_OVERRIDE_KEYS: &[u32] = &[{keys}];

#[inline]
fn mda_v2_cache_admit(key: usize) -> bool {{
    let flipped = MDA_V2_OVERRIDE_KEYS.binary_search(&(key as u32)).is_ok();
    if flipped {{ !MDA_V2_DEFAULT_ADMIT }} else {{ MDA_V2_DEFAULT_ADMIT }}
}}
"""
    c=replace_once(c,FEATURE_HELPER,FEATURE_HELPER+"\n"+policy_src,"policy source")
    open_new=r"""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            let cell = mda_v2_open_cell(e, depth).expect("memoized open expression must have a V2 cell");
            if mda_v2_cache_admit(cell) {
                if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                    return v;
                }
                let v = self.eval_no_cache(depth, te, e);
                self.tc_cache.open_eval_cache.insert(key, v);
                return v;
            }
            return self.eval_no_cache(depth, te, e);
        }
"""
    c=replace_once(c,OPEN_OLD,open_new,"open eval policy")
    dest.write_text(c)

def parse_timings(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        label,w,rep,wall=line.split("\t")
        rows.append({"label":label,"workload":w,"rep":int(rep),"wall":float(wall)})
    return rows

def summarize(rows):
    g={}
    for r in rows:g.setdefault((r["label"],r["workload"]),[]).append(r["wall"])
    out={}
    for (label,w),vals in g.items():
        out.setdefault(label,{})[w]={"values":vals,"median":statistics.median(vals)}
    return out

def select_policy(timing_path,policy_dir,out):
    s=summarize(parse_timings(timing_path))
    base=s["BASE"]; workloads=sorted(base)
    base_score=sum(base[w]["median"] for w in workloads)
    candidates=[]
    for label in sorted(s):
        if label in ("BASE","all_bypass"): continue
        if any(w not in s[label] for w in workloads): continue
        score=sum(s[label][w]["median"] for w in workloads)
        regs={w:s[label][w]["median"]/base[w]["median"]-1 for w in workloads}
        p=json.loads((Path(policy_dir)/f"{label}.json").read_text())
        candidates.append({
            "label":label,"score":score,"improvement":1-score/base_score,
            "regressions":regs,"eligible":all(v<=0.10 for v in regs.values()),
            "bypassed_observed_cells":p["bypassed_observed_cells"],
            "h":p["h"],"r":p["r"]
        })
    eligible=[x for x in candidates if x["eligible"]]
    eligible.sort(key=lambda x:(x["score"],x["bypassed_observed_cells"],x["h"],x["r"],x["label"]))
    selected=eligible[0] if eligible else None
    decision="UNKNOWN_NO_TRAINING_WIN_V2"
    if selected and selected["improvement"]>=0.01:
        decision="SELECT"
    payload={"schema":"mda-autonomous-cache-selection-v2","base_score":base_score,
             "workloads":workloads,"timings":s,"candidates":candidates,
             "selected":selected,"decision":decision}
    Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print("MDA_V2_SELECTION_DECISION="+decision)
    if selected:
        print("MDA_V2_SELECTION_LABEL="+selected["label"])
        print("MDA_V2_SELECTION_METRICS="+json.dumps(selected,sort_keys=True,separators=(",",":")))
    if decision!="SELECT":
        raise SystemExit(20)

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
    a=sp.add_parser("instrument"); a.add_argument("eval"); a.add_argument("main")
    a=sp.add_parser("parse-census"); a.add_argument("out"); a.add_argument("paths",nargs="+")
    a=sp.add_parser("make-policies"); a.add_argument("census"); a.add_argument("outdir")
    a=sp.add_parser("apply-policy"); a.add_argument("clean_eval"); a.add_argument("policy"); a.add_argument("dest")
    a=sp.add_parser("select"); a.add_argument("timings"); a.add_argument("policy_dir"); a.add_argument("out")
    args=ap.parse_args()
    if args.cmd=="instrument": instrument(Path(args.eval),Path(args.main))
    elif args.cmd=="parse-census": parse_census(args.paths,args.out)
    elif args.cmd=="make-policies": make_policies(args.census,args.outdir)
    elif args.cmd=="apply-policy": apply_policy(Path(args.clean_eval),Path(args.policy),Path(args.dest))
    elif args.cmd=="select": select_policy(args.timings,args.policy_dir,args.out)

if __name__=="__main__":
    main()
