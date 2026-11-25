"""Compare actual work of three source-pinned checkers under one safe ISA.

Profiles are Callgrind guest instructions, not Arena hardware-retired
instructions. No profile from a partial or non-accepting execution is scored.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time

spec=importlib.util.spec_from_file_location("recovery",Path(__file__).with_name("recovery.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture",required=True,type=Path)
    p.add_argument("--test",required=True)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--arms",nargs="+",choices=["flash","soko","nano"],required=True)
    p.add_argument("--timeout",type=int,default=1800)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    fixture=a.fixture.resolve()
    tests=m.source_manifest(a.out)
    t=tests[a.test]
    assert t["outcome"]=="accept"
    assert fixture.stat().st_size==t["size"] and m.sha(fixture)==t["sha256"]
    m.dump(a.out/"input-identity.json",{"test":a.test,"sha256":t["sha256"],"size":t["size"]})
    root=a.root.resolve()
    cfg=m.config(a.out,1)
    commands={
        "flash":[str(root/"flash.bin"),str(cfg)],
        "soko":[str(root/"soko.bin"),"--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"],
        "nano":[str(root/"nano.bin"),"-q","-j","1",str(fixture)],
    }
    rows=[]
    for arm in a.arms:
        cmd=commands[arm]
        identity=m.sha(cmd[0])
        # Require an independent native ACCEPT before profiling.
        with fixture.open("rb") as inp,(a.out/(arm+".native.out")).open("wb") as so,(a.out/(arm+".native.err")).open("wb") as se:
            native=subprocess.run(["timeout","--kill-after=10","1800",*cmd],stdin=inp,stdout=so,stderr=se).returncode
        row={"arm":arm,"binary_sha256":identity,"input_sha256":t["sha256"],"native_exit":native}
        rows.append(row)
        m.dump(a.out/"profile-rows.json",rows)
        if native!=0:
            print("PROFILE_NATIVE_FAILURE",json.dumps(row),flush=True)
            continue
        cg=a.out/(arm+".callgrind")
        stderr=a.out/(arm+".callgrind.log")
        start=time.monotonic()
        with fixture.open("rb") as inp,(a.out/(arm+".profile.out")).open("wb") as so,stderr.open("wb") as se:
            rc=subprocess.run(["timeout","--kill-after=30",str(a.timeout),
                 "valgrind","--tool=callgrind","--collect-jumps=no",
                 "--separate-threads=no","--error-exitcode=97",
                 "--callgrind-out-file="+str(cg),*cmd],stdin=inp,stdout=so,stderr=se).returncode
        row.update({"profile_exit":rc,"profile_elapsed_s":round(time.monotonic()-start,3),
                    "diagnostic":stderr.read_text(errors="replace")[-1600:]})
        if rc==0 and cg.exists():
            # Only completed profiles with one explicit Ir total are admitted.
            raw=cg.read_text(errors="replace")
            event=re.findall(r"^events:\s+(.+)$",raw,re.M)
            summary=re.findall(r"^summary:\s+(\d+)\s*$",raw,re.M)
            if event==["Ir"] and len(summary)==1 and int(summary[0])>0:
                row["guest_Ir"]=int(summary[0])
                for scope in ("yes","no"):
                    with (a.out/(arm+".inclusive-"+scope+".txt")).open("wb") as f:
                        subprocess.run(["callgrind_annotate","--auto=no","--inclusive="+scope,
                                        "--threshold=99",str(cg)],stdout=f,stderr=subprocess.STDOUT,check=True)
                # Retain exact profile bytes rather than rely on annotated output alone.
                row["profile_sha256"]=m.sha(cg)
        m.dump(a.out/"profile-rows.json",rows)
        print("MATCHED_PROFILE",json.dumps(row),flush=True)
    complete=all(r.get("native_exit")==0 and r.get("profile_exit")==0 and r.get("guest_Ir",0)>0 for r in rows)
    result={"test":a.test,"complete":complete,"scope":"matched generic-x86-64 single-worker Callgrind guest Ir, NOT hardware PMU or Arena score","rows":rows}
    m.dump(a.out/"profile-summary.json",result)
    print("PROFILE_SUMMARY",json.dumps(result),flush=True)
    assert complete

if __name__=="__main__":main()
