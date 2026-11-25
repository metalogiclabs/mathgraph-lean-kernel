"""Qualify the actual composition; preserve raw verdicts, never relabel failure."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

spec = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("recovery.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def strict(row):
    return row["raw_exit"] == (0 if row["expected"] == "accept" else 1)

def portable(out, before, candidate):
    tests = m.source_manifest(out)
    fixtures = m.unpack_portable(out, tests)
    assert len(fixtures) == 230
    config = m.config(out)
    logs = out / "logs"
    logs.mkdir()
    names = ["bugs/nat-shift-huge", "bugs/rec-rule-proof-irrel-nested", "bugs/rec-rule-proof-irrel"]
    assert all(n in fixtures for n in names)
    expected_before = {names[0]:1, names[1]:0, names[2]:1}
    rows = []
    for name in names + sorted(set(fixtures) - set(names)):
        pair = {"name":name}
        for arm,binary in (("before",before),("candidate",candidate)):
            row = m.run_one([str(binary),str(config)], fixtures[name],
                int(tests[name].get("timeout") or 120), arm, logs, name)
            row["expected"] = tests[name]["outcome"]
            row["input_sha256"] = tests[name]["sha256"]
            pair[arm] = row
        rows.append(pair)
        m.dump(out/"paired-rows.json",rows)
        print("COMBINED_PAIR", json.dumps({"name":name, "expected":tests[name]["outcome"],
             "before":pair["before"]["raw_exit"],"after":pair["candidate"]["raw_exit"],
             "diagnostic":pair["candidate"]["stderr_tail"]}), flush=True)
        if len(rows) <= 3:
            m.dump(out/"target-rows.json",rows)
    assert all(r["before"]["raw_exit"] == expected_before[r["name"]]
               for r in rows[:3]), "Baseline source behavior changed"
    wrong = [r["name"] for r in rows if not strict(r["candidate"])]
    regress = [r["name"] for r in rows if strict(r["before"]) and not strict(r["candidate"])]
    summary = {"test_count":len(rows),"correct_strict":len(rows)-len(wrong),
        "wrong_or_nondecisive":wrong,"new_regressions":regress,
        "full_mathlib":"NOT_TESTED_HERE",
        "binary_sha256":{"before":m.sha(before),"candidate":m.sha(candidate)}}
    m.dump(out/"combined-portable-summary.json",summary)
    print("COMBINED_PORTABLE",json.dumps(summary),flush=True)
    assert not wrong, "Residual remains"

def full_mathlib(out, before, candidate, fixture):
    tests = m.source_manifest(out)
    expected = tests["mathlib"]
    assert fixture.stat().st_size == expected["size"] and m.sha(fixture) == expected["sha256"]
    m.dump(out/"mathlib-identity.json",{"sha256":expected["sha256"],"size":expected["size"]})
    cfg = m.config(out)
    logs = out/"logs"
    logs.mkdir()
    rows = []
    for i,(arm,binary) in enumerate((("before",before),("candidate",candidate),("candidate",candidate),("before",before))):
        r = m.run_one([str(binary),str(cfg)],fixture,4120,arm,logs,f"mathlib-{i}")
        r["binary_sha256"]=m.sha(binary)
        r["input_sha256"]=expected["sha256"]
        rows.append(r)
        m.dump(out/"mathlib-rows.json",rows)
        print("COMBINED_MATHLIB",json.dumps(r),flush=True)
    assert all(r["raw_exit"] == 0 for r in rows)
    m.dump(out/"mathlib-summary.json",{"status":"EXACT_CURRENT_MATHLIB_ACCEPT","rows":rows,
        "note":"Local timings not Arena retired instructions."})

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["portable","mathlib"])
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--before",type=Path,required=True)
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--mathlib",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    if a.mode=="portable":
        portable(a.out,a.before,a.candidate)
    else:
        assert a.mathlib
        full_mathlib(a.out,a.before,a.candidate,a.mathlib)
