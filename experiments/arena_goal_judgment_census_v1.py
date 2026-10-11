#!/usr/bin/env python3
"""Independently qualify and report source-pinned Soko goal-judgment census.

Two modes:
  portable TEST_ROOT OUT : 196 protected verdicts baseline vs instrumented,
                           plus causal five-case census on the same binary.
  mathlib FULL_EXPORT OUT: original full pinned Mathlib check with diagnostic
                           build, including startup, parsing and teardown.

Never count cache hits as new capabilities. The output contains frequencies,
NOT measured savings, unproven equivalences or PMU retired instructions.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ARENA = "leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc"
SOKO = "intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d"
SHA = "22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
SIZE = 6184415052
PORTABLE = ("init-prelude", "perf/grind-ring-5",
            "perf/magma-list-deep-n21", "perf/magma-list-pair-n7",
            "perf/fueled-chain")
FLAGS = ["--stdin", "--nat-extension", "--string-extension",
         "--axiom-allow-all", "--threads", "4"]
BIN = {
    "baseline": "/tmp/goal-census-baseline.bin",
    "instrumented": "/tmp/goal-census-instrumented.bin",
}

def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as fin:
        for block in iter(lambda: fin.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def extract(stderr):
    lines = [line for line in stderr.splitlines() if line.startswith("MG_GOAL_CENSUS=")]
    assert len(lines) == 1, ("MISSING_UNIQUE_CENSUS", len(lines), stderr[-1200:])
    data = json.loads(lines[0].split("=", 1)[1])
    assert data["infer_calls"] == data["infer_check_calls"] + data["infer_only_calls"]
    assert data["type_cache_eligible_hits"] == (
        data["type_cache_check_hits"] + data["type_cache_infer_only_hits"])
    assert data["raw_lambda_pi_opportunities"] <= data["root_lambda_declarations"]
    assert data["raw_lambda_pi_opportunities"] <= data["raw_pi_declared_types"]
    assert data["theorem_declarations"] <= data["def_like_declarations"]
    assert data["app_arg_checked"] <= data["app_arg_steps"]
    return data

def check(binary, path, flags, instrument=False, timeout=420):
    env = dict(os.environ)
    if instrument:
        env["MG_GOAL_CENSUS"] = "1"
    else:
        env.pop("MG_GOAL_CENSUS", None)
    start = time.monotonic()
    with path.open("rb") as fin:
        p = subprocess.run([binary, *flags], stdin=fin, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=timeout, env=env)
    stderr = p.stderr.decode(errors="replace")
    return {"rc": p.returncode, "wall_seconds": round(time.monotonic()-start,3),
            "stderr_tail": stderr[-1100:] if p.returncode else "",
            "census": extract(stderr) if instrument and p.returncode == 0 else None}

def run_portable(root, out):
    positives = sorted((root / "good").rglob("*.ndjson"))
    negatives = sorted((root / "bad").rglob("*.ndjson"))
    assert (len(positives),len(negatives)) == (125,71), "portable archive changed"
    rows=[]
    counts={"accepted":0,"rejected":0,"declined":0}
    for bucket, files in (("good",positives),("bad",negatives)):
        for file in files:
            pair={}
            for arm in ("baseline","instrumented"):
                pair[arm]=check(BIN[arm], file, FLAGS, instrument=(arm=="instrumented"))
            a,b=pair["baseline"],pair["instrumented"]
            assert a["rc"] == b["rc"], ("DIFFERENTIAL_VERDICT",str(file),pair)
            if bucket=="good":
                assert a["rc"] == 0, ("NEW_POSITIVE_FAILURE",str(file),pair)
            else:
                assert a["rc"] in (1,2), ("BAD_PROOF_ADMITTED",str(file),pair)
            key={0:"accepted",1:"rejected",2:"declined"}[a["rc"]]
            counts[key]+=1
            rows.append({"case":str(file.relative_to(root)),
                         "sha256":hash_file(file),"rc":a["rc"]})
    assert counts=={"accepted":125,"rejected":69,"declined":2},counts
    cases=[]
    for name in PORTABLE:
        path = root / "good" / (name+".ndjson")
        assert path.is_file(), name
        data=check(BIN["instrumented"],path,FLAGS,True,timeout=1200)
        assert data["rc"]==0,(name,data)
        cases.append({"name":name,"sha256":hash_file(path),
                      "census":data["census"]})
        print("MG_GOAL_PORTABLE_CASE="+json.dumps({
            "name":name,"census":data["census"]}),flush=True)
    report={"authority":"source-pinned Soko source diagnostic only",
            "source":SOKO,"arena":ARENA,
            "corpus":"Arena artifact 11505862349, 125 good + 71 bad",
            "protected196":{"count":196,**counts,"wrong":0,
                            "baseline_instrumented_verdicts_identical":True},
            "five_cases":cases,"verdicts":rows,
            "official_rank_qualified":False,
            "semantic_gain_claimed":False,"instruction_saving_claimed":False}
    (out/"portable-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print("MG_GOAL_PORTABLE_SUMMARY="+json.dumps({
        "protected196":report["protected196"],"five_census_count":len(cases),
        "semantic_gain_claimed":False,"instruction_saving_claimed":False}),flush=True)

def run_mathlib(data, out):
    assert data.is_file() and data.stat().st_size==SIZE,("WRONG_ORIGINAL_EXPORT_SIZE",data)
    observed=hash_file(data)
    assert observed==SHA,("WRONG_ORIGINAL_EXPORT_SHA",observed)
    measured=check(BIN["instrumented"],data,FLAGS,True,timeout=7500)
    assert measured["rc"]==0,("EXACT_FULL_MATHLIB_NOT_ACCEPTED",measured)
    c=measured["census"]
    assert c["def_like_declarations"]>100000,c
    report={"authority":"complete pinned Mathlib ACCEPT by source-pinned instrumented Soko",
            "source":SOKO,"arena":ARENA,"mathlib_sha256":SHA,
            "mathlib_size_bytes":SIZE,"threads":4,
            "input_mode":"stdin, diagnostic release binary (no official PGO)",
            "verdict":"ACCEPT","wall_seconds_with_diagnostic_overhead":measured["wall_seconds"],
            "counts":c,
            "cache_hit_fraction_of_nonvars": c["type_cache_eligible_hits"] /
                max(1,c["infer_nonvar_calls"]),
            "raw_root_lambda_pi_fraction_of_deflikes":c["raw_lambda_pi_opportunities"] /
                max(1,c["def_like_declarations"]),
            "estimated_instructions_saved":None,
            "hardware_retired_instructions":None,
            "official_rank_qualified":False,
            "semantic_fastpath_warranted":False,
            "next_gate":"source-typed expected-Pi/lambda proof checking A/B only if a broad consequential family exists"}
    (out/"mathlib-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print("MG_GOAL_MATHLIB_SUMMARY="+json.dumps({
        "accepted":True,"mathlib_sha256":SHA,"declarations":c["def_like_declarations"],
        "theorems":c["theorem_declarations"],
        "lambda_pi":c["raw_lambda_pi_opportunities"],
        "cache_hits":c["type_cache_eligible_hits"],
        "cache_scope_misses":c["type_cache_existing_ineligible_scope"],
        "cold_lambda":c["cold_lambda"],
        "cold_app":c["cold_app"],
        "no_rank_or_saved_instruction_claim":True
    }),flush=True)

if __name__=="__main__":
    assert len(sys.argv)==4,"usage: portable|mathlib INPUT OUT"
    mode=sys.argv[1]
    root=Path(sys.argv[2])
    out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    if mode=="portable":run_portable(root,out)
    elif mode=="mathlib":run_mathlib(root,out)
    else:raise ValueError(mode)
