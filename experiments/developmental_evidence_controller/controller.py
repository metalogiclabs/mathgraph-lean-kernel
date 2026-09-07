#!/usr/bin/env python3
"""Conservative, evidence-backed Arena experiment controller. No checker writes."""
import argparse, csv, hashlib, io, json, math, statistics, zipfile
from pathlib import Path

EMPTY = hashlib.sha256(b"").hexdigest()
KNOWN_FIXTURES = {
    "tests::util::reject_rec_rule_with_forged_lambda_domains",
    "tests::util::reject_unlisted_recursor",
}

def load_source(spec, directory):
    path = directory / (spec["id"] + "-evidence.zip")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"], spec["id"]
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        if spec["id"] == "v61":
            rows = list(csv.DictReader(io.StringIO(z.read("timings.csv").decode())))
            measures = {}
            for corpus in ("cedar", "mathlib"):
                arms = {}
                for arm in ("soko", "candidate"):
                    xs = [float(r["seconds"]) for r in rows
                          if r["test"] == corpus and r["arm"] == arm]
                    assert len(xs) == 5
                    arms[arm] = statistics.median(xs)
                measures[corpus] = {
                    "control_median": arms["soko"],
                    "candidate_median": arms["candidate"],
                    "delta_percent": 100 * (arms["candidate"] / arms["soko"] - 1),
                }
            summary = z.read("summary.txt").decode()
            assert "PROMOTE_SOKO_PI_PROP_TO_ARENA_RELEASE_GATE" in summary
            assert all(v["delta_percent"] < 0 for v in measures.values())
            return {**spec, "status":"MEASURED_POSITIVE", "measures":measures,
                    "semantics":"HISTORICAL_RUN_CERTIFIED", "release_qualified":False}
        d = json.loads(z.read("results.json"))
        if spec["id"] == "v88":
            assert d["status"] == "FAILED" and not d["corpora"]
            assert "FileNotFoundError" in d["error"]
            q = json.loads(z.read("qualification.json"))
            assert q["no_new_test_failures"]
            assert set(q["control"]["failures"]) == KNOWN_FIXTURES
            assert set(q["candidate"]["failures"]) == KNOWN_FIXTURES
            return {**spec, "status":"INFRASTRUCTURE_NEGATIVE",
                    "residual":"std.ndjson missing; generated corpus is init-prelude.ndjson",
                    "semantics":"NOT_RUN", "measures":{},
                    "release_qualified":False}
        measures = {}
        for corpus, entry in (d.get("corpora") or d).items():
            ref, cand = entry["reference"], entry["candidate"]
            assert ref["rc"] == cand["rc"] == 0
            assert ref["stdout_sha256"] == cand["stdout_sha256"] == EMPTY
            assert ref["stderr_sha256"] == cand["stderr_sha256"] == EMPTY
            runs = entry["runs"]
            for arm in ("control", "candidate"):
                xs = [r for r in runs if r["arm"] == arm]
                assert len(xs) == 5
                assert {r["pass"] for r in xs} == set(range(5))
                assert all(r["rc"] == 0 and r["stdout_sha256"] == EMPTY
                           and r["stderr_sha256"] == EMPTY for r in xs)
                median = statistics.median(r["seconds"] for r in xs)
                assert math.isclose(median, entry[arm+"_median"], rel_tol=1e-10)
            delta = 100 * (entry["candidate_median"]/entry["control_median"]-1)
            assert math.isclose(delta,entry["delta_percent"],abs_tol=1e-8)
            measures[corpus] = {
                "control_median":entry["control_median"],
                "candidate_median":entry["candidate_median"],
                "delta_percent":delta}
        assert set(measures) == {"std","cedar","mathlib"}
        return {**spec, "status":"MEASURED_REGRESSION" if all(
                    v["delta_percent"] > 0 for v in measures.values()) else "MIXED",
                "measures":measures, "semantics":"EXACT_REPLAY_PASS",
                "release_qualified":False}

def learn(history):
    """Only a narrow, reversible search constraint; no claimed universal no-go."""
    negatives = [r for r in history if r["family"]=="cache_reset_reuse"
                 and r["status"]=="MEASURED_REGRESSION"]
    return {"cache_reset_reuse":{
        "negative_count":len(negatives),
        "evidence":[r["run"] for r in negatives],
        "require_new_separator":len(negatives)>=1,
        "scope":"Equivalent unmeasured cache-reset/reuse changes only",
        "revoke_when":"A new measured cost/attachment separator or positive counterexample is supplied"
    }}

def choose(history, policy=None):
    policy = learn(history) if policy is None else policy
    last=history[-1]
    if last["status"]=="INFRASTRUCTURE_NEGATIVE":
        return {"action":"REPAIR_HARNESS","target":last["residual"],
                "reason":"No benchmark result exists; retain the checker."}
    if last["status"]=="MEASURED_POSITIVE":
        return {"action":"REPEAT_AND_ABLATE","reason":"Positive local timing is not a release qualification."}
    if last["status"]=="MEASURED_REGRESSION":
        return {"action":"REJECT_CANDIDATE","reason":"Observed slowdown; preserve the incumbent."}
    return {"action":"DIAGNOSE_RESIDUAL","reason":"No admissible performance conclusion."}

def select_experiment(history, proposals, policy=None):
    policy = learn(history) if policy is None else policy
    if history[-1]["status"]=="INFRASTRUCTURE_NEGATIVE":
        return choose(history,policy)
    eligible=[]
    for p in proposals:
        if p.get("semantic_obligation") is None:
            continue
        constraint=policy.get(p["family"],{})
        if constraint.get("require_new_separator") and not p.get("new_measured_separator"):
            continue
        eligible.append(p)
    if not eligible:
        return {"action":"SEEK_SEPARATOR","reason":"No supplied candidate satisfies current evidence constraints."}
    return {"action":"VERIFY_CANDIDATE","candidate":eligible[0]["id"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("directory",type=Path)
    ap.add_argument("--out",type=Path,default=Path("results.json"))
    args=ap.parse_args()
    manifest=json.loads((args.directory/"sources.json").read_text())
    records=[load_source(s,args.directory) for s in manifest["sources"]]
    # Freeze on discovery; inspect heldout only after deriving the policy.
    frozen=learn(records[:2])
    heldout=records[2]
    observed=heldout["status"]=="MEASURED_REGRESSION"
    assert frozen["cache_reset_reuse"]["evidence"]==[34086097991]
    assert observed
    proposal={"id":"equivalent_cache_reuse","family":"cache_reset_reuse",
              "semantic_obligation":"Preserve reset boundaries"}
    learned=select_experiment(records[:2],[proposal],frozen)
    ablated=select_experiment(records[:2],[proposal],{})
    assert learned["action"]=="SEEK_SEPARATOR"
    assert ablated["action"]=="VERIFY_CANDIDATE"
    result={
        "schema":1,"incumbent":manifest["incumbent"],"records":records,
        "frozen_policy":frozen,
        "heldout":{"run":heldout["run"],"observed_regression":observed,
                   "learned_decision":learned,"ablated_decision":ablated,
                   "claim":"One historical prequential no-go check; not a demonstrated search-speedup."},
        "current_policy":learn(records[:3]),
        "next":choose(records),
        "release_promoted":False}
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("SOURCE_INTEGRITY=PASS")
    print("HISTORICAL_HELDOUT=PASS (one regression; no superiority claim)")
    print("POLICY_ABLATION=PASS (decision differs; no measured counterfactual cost)")
    print("NEXT="+result["next"]["action"])
    print("RELEASE_PROMOTED=false")

if __name__=="__main__":
    main()
