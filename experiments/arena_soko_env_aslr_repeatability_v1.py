#!/usr/bin/env python3
"""ASLR/hash-layout repeatability stress for one protected source-pinned sample.

Original proxy A/B generated 2.599B base, 2.564B env for magma-pair.
A later independent repeat gave 3.630B base but 2.557B candidate;
the 39.68% baseline outlier must not be counted as a causal improvement.
Pre-register eight fresh processes per arm, alternating which is first.
Measure whole-process Callgrind guest Ir, and report medians, MAD,
outlier rates, and median ratio.  No PMU or official ranking claim.
"""
import hashlib, json, math, pathlib, re, statistics, subprocess, sys, time
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
case=root/"good/perf/magma-list-pair-n7.ndjson"
assert case.is_file()
expected="abce636f6a7dd529c0dc6bbad8e7c8e2eaecfdda0d04c191d7f868e3a4468d35"
assert hashlib.sha256(case.read_bytes()).hexdigest()==expected
runs={"compound":[],"compound_env":[]}
opts=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"]
for i in range(8):
    order=["compound","compound_env"] if i%2==0 else ["compound_env","compound"]
    for arm in order:
        binary=f"/tmp/soko-repeat-{arm}"
        profile=out/f"guest-{arm}-{i}.callgrind"
        cmd=["valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
             f"--callgrind-out-file={profile}",binary,*opts]
        t=time.monotonic()
        with case.open("rb") as fin:
            p=subprocess.run(cmd,stdin=fin,stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE,timeout=650)
        assert p.returncode==0,(arm,i,p.returncode,p.stderr[-600:])
        m=re.search(r"^summary:\s*(\d+)\s*$",profile.read_text(),re.M)
        assert m,(arm,i,"Callgrind summary absent")
        ir=int(m.group(1)); assert ir>1_000_000
        runs[arm].append(ir)
        profile.unlink()
        print("ENV_ASLR_REPLAY_CASE="+json.dumps({"pair":i,"arm":arm,"Ir":ir,
            "seconds":round(time.monotonic()-t,3)}),flush=True)
med={a:statistics.median(xs) for a,xs in runs.items()}
mad={a:statistics.median(abs(x-med[a]) for x in xs) for a,xs in runs.items()}
outliers={a:sum(abs(x/med[a]-1)>0.2 for x in xs) for a,xs in runs.items()}
pairs=[runs["compound_env"][i]/runs["compound"][i] for i in range(8)]
summary={"input_sha256":expected,"run_count_per_arm":8,
         "full_corpus_correctness_from_separate_source_run":True,
         "guest_Ir_by_arm":runs,"median_Ir_by_arm":med,
         "MAD_Ir_by_arm":mad,"more_than_20pct_outliers":outliers,
         "ratio_median_candidate_to_baseline":med["compound_env"]/med["compound"],
         "paired_ratios":pairs,"geomean_pair_ratio":math.exp(sum(map(math.log,pairs))/len(pairs)),
         "ratio_extremes":[min(pairs),max(pairs)],
         "official_rank_qualified":False,
         "analysis":"Descriptive stability diagnosis; never treat outliers as causal wins"}
(out/"aslr_stability.json").write_text(json.dumps(summary,indent=2)+"\n")
print("ENV_ASLR_REPLAY_SUMMARY="+json.dumps(summary),flush=True)
