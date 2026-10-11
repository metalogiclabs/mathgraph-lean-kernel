#!/usr/bin/env python3
"""Causal 1/2/4-worker input-mode comparison, exact checker, pinned corpus.

Callgrind Ir is a guest instruction proxy, NOT hardware retired instructions.
Never promote a ranking claim from this experiment alone.
"""
import json, math, os, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
exe="/tmp/soko-serial-decision"
opts=["--nat-extension","--string-extension","--axiom-allow-all"]
cases=[("good",p) for p in sorted((root/"good").rglob("*.ndjson"))]+[
       ("bad",p) for p in sorted((root/"bad").rglob("*.ndjson"))]
assert len(cases)==196 and sum(t=="good" for t,_ in cases)==125
arms=[(t,mode) for t in (1,2,4) for mode in ("stdin","mapped")]
def command(path,threads,mode):
    return [exe,*([str(path)] if mode=="mapped" else ["--stdin"]),*opts,"--threads",str(threads)]
def run(path,threads,mode,callgrind=None):
    args=command(path,threads,mode)
    if callgrind:
        args=["valgrind","--tool=callgrind","--quiet","--collect-jumps=no",
              "--callgrind-out-file="+str(callgrind),*args]
    with path.open("rb") as f:
        return subprocess.run(args,stdin=f if mode=="stdin" else subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=360)
counts={}
for bucket,path in cases:
    verdicts={}
    for threads,mode in arms:
        p=run(path,threads,mode)
        verdicts[f"{threads}_{mode}"]=p.returncode
    assert len(set(verdicts.values()))==1,(path,verdicts)
    verdict=next(iter(verdicts.values()))
    assert verdict==0 if bucket=="good" else verdict in (1,2),(path,verdict)
    counts[str(verdict)]=counts.get(str(verdict),0)+1
print("SERIAL_DECISION_VERDICTS="+json.dumps({"count":len(cases),"outcomes":counts,
      "all_six_arms_identical":True}),flush=True)
focus=["init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain"]
records=[]
phase_profiles=[]
for case in focus:
    path=root/"good"/(case+".ndjson")
    assert path.is_file(),path
    values={}
    for threads,mode in arms:
        output=out/(case.replace("/","_")+f"-{threads}-{mode}.callgrind")
        p=run(path,threads,mode,output)
        assert p.returncode==0,(case,threads,mode,p.stderr[-700:])
        line=next((l for l in output.read_text().splitlines() if l.startswith("summary: ")),None)
        assert line is not None,(case,threads,mode)
        values[f"{threads}_{mode}"]=int(line.split()[1])
        if threads==1 and mode=="mapped":
            # A single precise representative profile; keep output and source
            # identity, but do not confuse Callgrind with the Arena PMU counter.
            annotated=subprocess.run(["callgrind_annotate","--threshold=97",str(output)],
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                     text=True,timeout=90)
            assert annotated.returncode==0,(case,annotated.stderr[-1000:])
            prefix=case.replace("/","_")
            (out/(prefix+"-full-hotspots.txt")).write_text(annotated.stdout)
            parse_file=out/(prefix+"-parse.callgrind")
            parse_cmd=[exe,*([str(path)]),"--parse-only",*opts,"--threads","1"]
            pparse=subprocess.run(["valgrind","--tool=callgrind","--quiet",
                      "--collect-jumps=no","--callgrind-out-file="+str(parse_file),
                      *parse_cmd],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                      timeout=360)
            assert pparse.returncode==0,(case,pparse.stderr[-700:])
            parse_line=next((l for l in parse_file.read_text().splitlines()
                              if l.startswith("summary: ")),None)
            assert parse_line is not None,case
            parse_ir=int(parse_line.split()[1])
            parse_annotated=subprocess.run(["callgrind_annotate","--threshold=97",str(parse_file)],
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                     text=True,timeout=90)
            assert parse_annotated.returncode==0,(case,parse_annotated.stderr[-1000:])
            (out/(prefix+"-parse-hotspots.txt")).write_text(parse_annotated.stdout)
            assert 0 < parse_ir <= values["1_mapped"],(case,parse_ir,values["1_mapped"])
            profile={"case":case,"parse_guest_Ir":parse_ir,
                     "full_guest_Ir":values["1_mapped"],
                     "whole_process_parse_fraction":parse_ir/values["1_mapped"],
                     "full_profile":prefix+"-full-hotspots.txt",
                     "parse_profile":prefix+"-parse-hotspots.txt"}
            phase_profiles.append(profile)
            print("HOTSPOT_PHASE_CASE="+json.dumps(profile),flush=True)
            parse_file.unlink()
        output.unlink()
    record={"case":case,"guest_instructions":values,
            "serial_over_four_stdin":values["1_stdin"]/values["4_stdin"],
            "serial_over_four_mapped":values["1_mapped"]/values["4_mapped"],
            "mapped_serial_over_streamed_four":values["1_mapped"]/values["4_stdin"]}
    records.append(record)
    print("SERIAL_DECISION_CASE="+json.dumps(record),flush=True)
metrics=["serial_over_four_stdin","serial_over_four_mapped","mapped_serial_over_streamed_four"]
geomeans={k:math.exp(sum(math.log(v[k]) for v in records)/len(records)) for k in metrics}
decision="PROMOTE_TO_NATIVE_MATHLIB_MEASUREMENT" if geomeans["mapped_serial_over_streamed_four"]<0.99 else "NO_DECISIVE_PROXY_WIN"
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "experiment":os.environ["GITHUB_SHA"],"verdict_counts":counts,
        "measure":"Valgrind Callgrind guest Ir, NOT Arena hardware retired instructions",
        "cases":records,"phase_profiles":phase_profiles,
        "phase_subtraction_is_approximate":True,
        "geometric_means":geomeans,"decision":decision,
        "official_rank_qualified":False}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("SERIAL_DECISION_SUMMARY="+json.dumps({"geomeans":geomeans,"decision":decision}),flush=True)
