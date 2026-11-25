"""Matched input benchmark: build-only PGO, thread count ablation, pinned champion.
The training export is Init; the measured holdout is the complete exact
current Arena Mathlib. This is not a submission and never relabels a failure.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import time

spec=importlib.util.spec_from_file_location("recovery",Path(__file__).with_name("recovery.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def input_identity(out, fixture, name):
    t=m.source_manifest(out)[name]
    got={"sha256":m.sha(fixture),"size":fixture.stat().st_size}
    assert got=={"sha256":t["sha256"],"size":t["size"]},(name,got,t)
    m.dump(out/(name+"-identity.json"),got)
    return t

def execute(cmd, fixture, out, tag, timeout, pmu):
    stderr=out/(tag+".stderr")
    stdout=out/(tag+".stdout")
    timing=out/(tag+".time")
    perf=out/(tag+".perf")
    argv=["/usr/bin/time","-f","%e %U %S %M","-o",str(timing)]
    if pmu:
        argv+=["perf","stat","-x,","-o",str(perf),"-e","instructions:u","--"]
    argv+=cmd
    start=time.monotonic()
    with fixture.open("rb") as inp,stdout.open("wb") as so,stderr.open("wb") as se:
        p=subprocess.Popen(argv,stdin=inp,stdout=so,stderr=se,start_new_session=True)
        try: rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL)
            p.wait()
            rc="TIMEOUT"
    row={"exit":rc,"elapsed":round(time.monotonic()-start,3),
         "stderr_tail":stderr.read_bytes()[-1200:].decode(errors="replace")}
    if timing.exists():
        fields=timing.read_text().strip().splitlines()[-1].split()
        if len(fields)==4:
            row.update(dict(zip(("wall","user","system","rss_kb"),map(float,fields))))
    if perf.exists():
        row["perf_raw"]=perf.read_text()
        for line in row["perf_raw"].splitlines():
            cells=line.split(",")
            if len(cells)>=3 and cells[2]=="instructions:u":
                try: row["instructions"]=int(cells[0])
                except ValueError: pass
    return row

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["identity","measure"])
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True)
    p.add_argument("--name",default="init")
    p.add_argument("--root",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    t=input_identity(a.out,a.fixture,a.name)
    if a.mode=="identity": return
    assert a.name=="mathlib" and a.root is not None
    root=a.root.resolve()
    logs=a.out/"measurements";logs.mkdir(exist_ok=True)
    cfg2=m.config(a.out,2);cfg4=m.config(a.out,4)
    commands={
        "base2":[str(root/"baseline"),str(cfg2)],
        "pgo2":[str(root/"pgo"),str(cfg2)],
        "base4":[str(root/"baseline"),str(cfg4)],
        "pgo4":[str(root/"pgo"),str(cfg4)],
        "nano4":[str(root/"nano/target/release/nl-fast"),"-q","-j","4",str(a.fixture)],
    }
    probe=subprocess.run(["perf","stat","-e","instructions:u","--","true"],
                         capture_output=True) if Path("/usr/bin/perf").exists() else None
    pmu=probe is not None and probe.returncode==0
    (a.out/"pmu-probe.txt").write_bytes((probe.stdout+probe.stderr) if probe else b"perf unavailable")
    hashes={k:m.sha(v[0]) for k,v in commands.items()}
    rows=[]
    order=["base2","pgo2","base4","pgo4","nano4","nano4","pgo4","base4","pgo2","base2"]
    for i,arm in enumerate(order):
        row=execute(commands[arm],a.fixture,logs,f"{i:02d}-{arm}",int(t["timeout"]),pmu)
        row.update({"arm":arm,"binary_sha256":hashes[arm],"input_sha256":t["sha256"]})
        rows.append(row);m.dump(a.out/"pgo-rows.json",rows)
        print("PGO_MATHLIB",json.dumps(row),flush=True)
    medians={}
    for arm in commands:
        rs=[r for r in rows if r["arm"]==arm]
        if len(rs)==2 and all(r["exit"]==0 and "user" in r for r in rs):
            v={"wall_s":statistics.median(r["wall"] for r in rs),
               "cpu_s":statistics.median(r["user"]+r["system"] for r in rs),
               "max_rss_kb":max(r["rss_kb"] for r in rs)}
            if all("instructions" in r for r in rs):
                v["instructions"]=statistics.median(r["instructions"] for r in rs)
            medians[arm]=v
    summary={"scope":"matched local complete Mathlib; not official Arena rank",
             "pmu_permitted":pmu,"medians":medians,"all_accept":len(medians)==len(commands),
             "training":"exact Init for Flash; champion original pinned build",
             "selection":"none until all accepted and measured; full selected build requalification required"}
    m.dump(a.out/"pgo-summary.json",summary)
    print("PGO_SUMMARY",json.dumps(summary),flush=True)
    assert summary["all_accept"]
if __name__=="__main__": main()
