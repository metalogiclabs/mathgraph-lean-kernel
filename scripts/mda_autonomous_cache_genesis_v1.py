#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, statistics
from pathlib import Path

ROOTS=["App","Proj","Let","Pi","Lambda"]
MASKS=["0","1_4","5_8","9_16","17_32","33_64"]
DEPTHS=["0","1_2","3_7","8_plus"]
NCELLS=len(ROOTS)*len(MASKS)*len(DEPTHS)

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

FEATURE_HELPER="""
const MDA_OPEN_ROOTS: usize = 5;
const MDA_OPEN_MASKS: usize = 6;
const MDA_OPEN_DEPTHS: usize = 4;
const MDA_OPEN_CELLS: usize = MDA_OPEN_ROOTS * MDA_OPEN_MASKS * MDA_OPEN_DEPTHS;

#[inline]
fn mda_open_root(e: ExprPtr<'_>) -> Option<usize> {
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
fn mda_open_mask(e: ExprPtr<'_>) -> usize {
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
fn mda_open_depth(depth: u32) -> usize {
    match depth {
        0 => 0,
        1..=2 => 1,
        3..=7 => 2,
        _ => 3,
    }
}

#[inline]
fn mda_open_cell(e: ExprPtr<'_>, depth: u32) -> Option<usize> {
    let r = mda_open_root(e)?;
    Some((r * MDA_OPEN_MASKS + mda_open_mask(e)) * MDA_OPEN_DEPTHS + mda_open_depth(depth))
}
"""

CENSUS_EXTRA="""
static MDA_OPEN_HITS: [AtomicU64; MDA_OPEN_CELLS] = [const { AtomicU64::new(0) }; MDA_OPEN_CELLS];
static MDA_OPEN_MISSES: [AtomicU64; MDA_OPEN_CELLS] = [const { AtomicU64::new(0) }; MDA_OPEN_CELLS];

pub fn mda_report_open_cache_census() {
    if std::env::var_os("MDA_CACHE_CENSUS").is_none() {
        return;
    }
    const ROOT_NAMES: [&str; MDA_OPEN_ROOTS] = ["App","Proj","Let","Pi","Lambda"];
    const MASK_NAMES: [&str; MDA_OPEN_MASKS] = ["0","1_4","5_8","9_16","17_32","33_64"];
    const DEPTH_NAMES: [&str; MDA_OPEN_DEPTHS] = ["0","1_2","3_7","8_plus"];
    for r in 0..MDA_OPEN_ROOTS {
        for m in 0..MDA_OPEN_MASKS {
            for d in 0..MDA_OPEN_DEPTHS {
                let i = (r * MDA_OPEN_MASKS + m) * MDA_OPEN_DEPTHS + d;
                let h = MDA_OPEN_HITS[i].load(Ordering::Relaxed);
                let x = MDA_OPEN_MISSES[i].load(Ordering::Relaxed);
                if h != 0 || x != 0 {
                    eprintln!(
                        "MDA_CACHE_CELL idx={} root={} mask={} depth={} hits={} misses={}",
                        i, ROOT_NAMES[r], MASK_NAMES[m], DEPTH_NAMES[d], h, x
                    );
                }
            }
        }
    }
}
"""

CENSUS_OPEN="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            let cell = mda_open_cell(e, depth);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                if let Some(i) = cell {
                    MDA_OPEN_HITS[i].fetch_add(1, Ordering::Relaxed);
                }
                return v;
            }
            if let Some(i) = cell {
                MDA_OPEN_MISSES[i].fetch_add(1, Ordering::Relaxed);
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }
"""

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
    c=replace_once(c,"use std::cell::OnceCell;\n",
        "use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};\n","atomic import")
    c=add_feature_helper(c)
    anchor=FEATURE_HELPER
    c=replace_once(c,anchor,anchor+"\n"+CENSUS_EXTRA,"census statics")
    c=replace_once(c,OPEN_OLD,CENSUS_OPEN,"open eval census")
    eval_path.write_text(c)

    m=main_path.read_text()
    m=replace_once(m,"    export_file.check_all_declars();\n",
        "    export_file.check_all_declars();\n    sokonanoda::eval::mda_report_open_cache_census();\n","main census report")
    main_path.write_text(m)

CELL_RE=re.compile(r"MDA_CACHE_CELL idx=(\d+) root=(\S+) mask=(\S+) depth=(\S+) hits=(\d+) misses=(\d+)")

def parse_census(paths, out):
    rows=[{"idx":i,"root":ROOTS[(i//len(DEPTHS))//len(MASKS)],
           "mask":MASKS[(i//len(DEPTHS))%len(MASKS)],
           "depth":DEPTHS[i%len(DEPTHS)],"hits":0,"misses":0} for i in range(NCELLS)]
    by={r["idx"]:r for r in rows}
    sources=[]
    for pstr in paths:
        p=Path(pstr); sources.append(str(p))
        for line in p.read_text(errors="replace").splitlines():
            m=CELL_RE.search(line)
            if not m: continue
            idx,root,mask,depth,hits,misses=m.groups()
            r=by[int(idx)]
            assert (r["root"],r["mask"],r["depth"])==(root,mask,depth)
            r["hits"]+=int(hits); r["misses"]+=int(misses)
    for r in rows:
        t=r["hits"]+r["misses"]
        r["events"]=t
        r["hit_ratio"]=r["hits"]/t if t else 0.0
    payload={"schema":"mda-autonomous-cache-census-v1","sources":sources,"cells":rows,
             "totals":{"hits":sum(r["hits"] for r in rows),"misses":sum(r["misses"] for r in rows)}}
    Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")

def make_policies(census_path,outdir):
    d=json.loads(Path(census_path).read_text())
    cells=d["cells"]
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    hs=[1,2,4,8,16]; rs=[0.0,0.01,0.05,0.10,0.20,0.40]
    labels=[]
    for h in hs:
        for ratio in rs:
            admit=[(c["hits"]>=h and c["hit_ratio"]>=ratio) for c in cells]
            label=f"h{h}_r{str(ratio).replace('.','p')}"
            payload={"schema":"mda-cache-policy-v1","label":label,"h":h,"r":ratio,
                     "admit":admit,"admitted_cells":sum(admit),
                     "source":"training_census_only"}
            (out/f"{label}.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
            labels.append(label)
    # negative control, timed but excluded from synthesized promotion
    payload={"schema":"mda-cache-policy-v1","label":"all_bypass","h":None,"r":None,
             "admit":[False]*NCELLS,"admitted_cells":0,"source":"negative_control"}
    (out/"all_bypass.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    (out/"labels.txt").write_text("\n".join(labels+["all_bypass"])+"\n")

def apply_policy(clean_eval:Path, policy_path:Path, dest:Path):
    c=clean_eval.read_text()
    p=json.loads(policy_path.read_text())
    admit=p["admit"]
    if len(admit)!=NCELLS: raise SystemExit("wrong policy size")
    c=add_feature_helper(c)
    vals=", ".join("true" if x else "false" for x in admit)
    table=f"\nconst MDA_OPEN_CACHE_ADMIT: [bool; MDA_OPEN_CELLS] = [{vals}];\n"
    c=replace_once(c,FEATURE_HELPER,FEATURE_HELPER+table,"policy table")
    new="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            let cell = mda_open_cell(e, depth).expect("open memoized expression has a policy cell");
            if MDA_OPEN_CACHE_ADMIT[cell] {
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
    c=replace_once(c,OPEN_OLD,new,"open eval policy")
    dest.write_text(c)

def parse_timings(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        label,workload,rep,wall=line.split("\t")
        rows.append({"label":label,"workload":workload,"rep":int(rep),"wall":float(wall)})
    return rows

def summarize_timings(rows):
    g={}
    for r in rows:
        g.setdefault((r["label"],r["workload"]),[]).append(r["wall"])
    s={}
    for (label,w),vals in g.items():
        s.setdefault(label,{})[w]={"values":vals,"median":statistics.median(vals)}
    return s

def select_policy(timing_path,policy_dir,out):
    rows=parse_timings(timing_path)
    s=summarize_timings(rows)
    if "BASE" not in s: raise SystemExit("BASE missing")
    base=s["BASE"]
    workloads=sorted(base)
    base_score=sum(base[w]["median"] for w in workloads)
    candidates=[]
    for label in sorted(s):
        if label in ("BASE","all_bypass"): continue
        if any(w not in s[label] for w in workloads): continue
        score=sum(s[label][w]["median"] for w in workloads)
        regressions={w:s[label][w]["median"]/base[w]["median"]-1 for w in workloads}
        eligible=all(x<=0.10 for x in regressions.values())
        policy=json.loads((Path(policy_dir)/f"{label}.json").read_text())
        candidates.append({"label":label,"score":score,"improvement":1-score/base_score,
                           "regressions":regressions,"eligible":eligible,
                           "admitted_cells":policy["admitted_cells"],
                           "h":policy["h"],"r":policy["r"]})
    eligible=[x for x in candidates if x["eligible"]]
    eligible.sort(key=lambda x:(x["score"],x["admitted_cells"],x["h"],x["r"],x["label"]))
    selected=eligible[0] if eligible else None
    decision="UNKNOWN_NO_TRAINING_WIN"
    if selected and selected["improvement"]>=0.01:
        decision="SELECT"
    payload={"schema":"mda-autonomous-cache-selection-v1","base_score":base_score,
             "workloads":workloads,"timings":s,"candidates":candidates,
             "selected":selected,"decision":decision}
    Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print("MDA_SELECTION_DECISION="+decision)
    if selected: print("MDA_SELECTION_LABEL="+selected["label"])
    if decision!="SELECT": raise SystemExit(20)

def heldout(timing_path,selected_label,out):
    rows=parse_timings(timing_path); s=summarize_timings(rows)
    base=s["BASE"]; cand=s[selected_label]; workloads=sorted(base)
    bm={w:base[w]["median"] for w in workloads}; cm={w:cand[w]["median"] for w in workloads}
    improve={w:1-cm[w]/bm[w] for w in workloads}
    agg=1-sum(cm.values())/sum(bm.values())
    wins=sum(1 for v in improve.values() if v>0)
    max_reg=max((-v for v in improve.values()),default=0)
    passed=agg>=0.01 and wins>=2 and max_reg<=0.05
    payload={"schema":"mda-autonomous-cache-heldout-v1","selected":selected_label,
             "base_medians":bm,"candidate_medians":cm,"per_workload_improvement":improve,
             "aggregate_improvement":agg,"wins":wins,"max_regression":max_reg,"pass":passed}
    Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print("MDA_HELDOUT="+json.dumps(payload,sort_keys=True))
    if not passed: raise SystemExit(21)

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
    a=sp.add_parser("instrument"); a.add_argument("eval"); a.add_argument("main")
    a=sp.add_parser("parse-census"); a.add_argument("out"); a.add_argument("paths",nargs="+")
    a=sp.add_parser("make-policies"); a.add_argument("census"); a.add_argument("outdir")
    a=sp.add_parser("apply-policy"); a.add_argument("clean_eval"); a.add_argument("policy"); a.add_argument("dest")
    a=sp.add_parser("select"); a.add_argument("timings"); a.add_argument("policy_dir"); a.add_argument("out")
    a=sp.add_parser("heldout"); a.add_argument("timings"); a.add_argument("selected"); a.add_argument("out")
    args=ap.parse_args()
    if args.cmd=="instrument": instrument(Path(args.eval),Path(args.main))
    elif args.cmd=="parse-census": parse_census(args.paths,args.out)
    elif args.cmd=="make-policies": make_policies(args.census,args.outdir)
    elif args.cmd=="apply-policy": apply_policy(Path(args.clean_eval),Path(args.policy),Path(args.dest))
    elif args.cmd=="select": select_policy(args.timings,args.policy_dir,args.out)
    elif args.cmd=="heldout": heldout(args.timings,args.selected,args.out)

if __name__=="__main__": main()
