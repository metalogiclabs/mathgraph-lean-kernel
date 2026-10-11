#!/usr/bin/env python3
"""Source-pinned Π-lambda adversarial negative controls.

For two fixed official valid exports, select the last bona fide def/theorem
whose root value is a Lam and whose declared type is a Pi. Generate (1) a
wrong-domain typed lambda, and (2) a wrong-body typed lambda by replacing
one referenced field with a previously declared exact Sort expression.
All other original-source records are byte-identical.

The source metadata and DAG indices remain parseable; baseline, candidate
and original-check shadow must reject both false proofs. These mutants
cannot prove universal soundness and do not change protected 196.
"""
import copy,hashlib,json,os,pathlib,subprocess,sys

root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
good=("init-prelude","perf/magma-list-pair-n7","perf/fueled-chain")
bins={"baseline":"/tmp/goal-negative-baseline.bin",
      "candidate":"/tmp/goal-negative-candidate.bin"}
opts=["--stdin","--nat-extension","--string-extension",
      "--axiom-allow-all","--threads","4"]

def sha(blob):return hashlib.sha256(blob).hexdigest()

def make_mutants(path):
    raw=path.read_bytes()
    lines=raw.splitlines(keepends=True)
    rows=[json.loads(x) for x in lines]
    expr={r["ie"]:(idx,r) for idx,r in enumerate(rows) if "ie" in r}
    candidates=[]
    for index,r in enumerate(rows):
        for declkind in ("def","thm"):
            if declkind not in r:continue
            d=r[declkind]
            val=expr.get(d.get("value"))
            ty=expr.get(d.get("type"))
            if val is not None and ty is not None and "lam" in val[1] and "forallE" in ty[1]:
                candidates.append((index,declkind,d,val,ty))
    assert candidates,("NO_TYPE_DIRECTED_LAMBDA_GOAL",path)
    _,kind,decl,(lam_idx,lamrow),(type_idx,tyrow)=candidates[-1]
    used=lamrow["lam"]
    sorts=[eid for eid,(_,row) in expr.items() if "sort" in row and eid!=used["type"]]
    assert sorts,("NO_WELL_FORMED_SORT_MUTANT",path)
    replacement=sorts[0]
    variants=[]
    for variant,field in (("wrong_domain","type"),("wrong_dependent_body","body")):
        assert used[field]!=replacement,("NO_REAL_MUTATION",variant)
        changed=copy.deepcopy(lamrow)
        changed["lam"][field]=replacement
        modified=list(lines)
        modified[lam_idx]=json.dumps(changed,ensure_ascii=False,separators=(",",":")).encode()+b"\n"
        altered=b"".join(modified)
        assert altered!=raw and sha(altered)!=sha(raw)
        target={"variant":variant,"declaration_kind":kind,
                "declaration_value_id":decl["value"],
                "declaration_type_id":decl["type"],
                "lambda_expression_id":lamrow["ie"],
                "lambda_field":field,
                "original_referenced_expr_id":used[field],
                "replacement_sort_expr_id":replacement,
                "original_sha256":sha(raw),"mutated_sha256":sha(altered)}
        variants.append((target,altered))
    return raw,variants

def invoke(data,arm,shadow=False):
    env=dict(os.environ)
    env.pop("MG_PI_CHECK_SHADOW",None)
    env.pop("MG_PI_REPORT",None)
    if arm=="candidate":
        env["MG_PI_REPORT"]="1"
        if shadow:env["MG_PI_CHECK_SHADOW"]="1"
    p=subprocess.run([bins[arm],*opts],input=data,env=env,
                     stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=300)
    return {"returncode":p.returncode,"stderr_tail":p.stderr[-1000:].decode(errors="replace")}

reports=[]
for case in good:
    path=root/"good"/(case+".ndjson")
    assert path.is_file(),path
    original,mutants=make_mutants(path)
    for arm in bins:
        v=invoke(original,arm)
        assert v["returncode"]==0,("POSITIVE_CONTROL_DRIFT",case,arm,v)
    shadow=invoke(original,"candidate",True)
    assert shadow["returncode"]==0,("POSITIVE_SHADOW_DRIFT",case,shadow)
    for meta,data in mutants:
        verdicts={}
        for arm in bins:
            verdicts[arm]=invoke(data,arm)
        verdicts["candidate_shadow"]=invoke(data,"candidate",True)
        codes=[x["returncode"] for x in verdicts.values()]
        assert all(rc in (1,2) for rc in codes),(
            "FORGED_LAMBDA_OR_DEPENDENT_PROOF_ACCEPTED_OR_INTERNAL_ERROR",case,meta,verdicts)
        assert len(set(codes))==1,("BASELINE_ORIGINAL_SEMANTIC_DISAGREEMENT",case,meta,verdicts)
        row={"case":case,**meta,"verdict":codes[0],"all_three_non_accept":True}
        reports.append(row)
        print("MG_GOAL_ADVERSARIAL_CASE="+json.dumps(row),flush=True)
assert len(reports)==len(good)*2
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
        "experiment_commit":os.environ.get("GITHUB_SHA"),
        "positive_controls":list(good),
        "synthetic_mutants":reports,
        "all_mutants_non_accept":True,
        "no_unverified_semantic_promotion":True,
        "full_mathlib_and_pmu_not_tested":True}
(out/"adversarial-report.json").write_text(json.dumps(report,indent=2)+"\n")
print("MG_GOAL_ADVERSARIAL_SUMMARY="+json.dumps({
    "positive_controls":len(good),"mutants_non_accept":len(reports),
    "unsafe_accepts":0,"authoritative_scope":"six source-locked mutants only"}),flush=True)
