#!/usr/bin/env python3
"""Exact-source diagnostic of Rust full-export parse vs selected proof checking.

No parser reuse, caching or new acceptance authority is implemented here.
Both executables use the same Rust parser and selected kernel over the same
pinned genuine Lean/Std export. The profiled executable reports parse and
actual selected proof-check phases; original selected checker is the oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
from datetime import datetime, timezone

from qualify_delta import (configuration, file_hash, fresh_index,
                           independent_partition, command_run, write)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VARIANTS = ("early-definition", "unrelated-definition")
EXPECTED = {
    "original": {"baseline": 3436, "early-definition": 413,
                 "unrelated-definition": 1},
    "expanded": {"baseline": 11653, "early-definition": 672,
                 "unrelated-definition": 260},
}
NEGATIVES = ("malformed-unused-dag", "malformed-unused-typed-node", "invalid-proof")

def require(value, message):
    if not value:
        raise ValueError(message)

def exact_contract(raw, num, total, profiled):
    o = json.loads(raw)
    expected_keys = {"checked", "total_declarations", "scope"}
    require(type(o) is dict and expected_keys <= set(o), "missing actual-kernel fields")
    require(o["scope"] == "selected_obligations_under_caller_trusted_environment",
            "not genuine selected kernel")
    require(type(o["checked"]) is int and o["checked"] == num and
            type(o["total_declarations"]) is int and o["total_declarations"] == total,
            "selected kernel counts differ from independently derived obligations")
    if profiled:
        require(o.get("profiling_scope") ==
                "diagnostic_exact_full_parser_and_actual_selected_kernel",
                "profile must parse and check the actual development")
        for name in ("setup_seconds","parse_seconds","selected_check_seconds","total_seconds"):
            require(type(o.get(name)) is float and 0 <= o[name] < 120,
                    "missing/invalid Rust profiling phase: "+name)
        require(o["parse_seconds"] + o["selected_check_seconds"] <=
                o["total_seconds"] + 0.00001, "parser timings do not fit total")
    return o

def timed_checker(binary, config, selected, outfile):
    record, stdout = command_run(
        [binary, config, selected], outfile, timeout=180)
    return record, stdout

def preflight(args):
    manifest = json.loads((args.workloads / "manifest.json").read_bytes())
    pins = json.loads((HERE / "pins.json").read_bytes())
    profile = manifest.get("profile", "original-v1")
    if profile == "std-hashmap-expanded-v1":
        expanded = json.loads((HERE / "delta-pins.json").read_bytes())
        expected = expanded["export_sha256"]
        label = "expanded"
    else:
        expected = pins["export_sha256"]
        label = "original"
    require(label == args.profile, "wrong pinned Lean export profile")
    for name, digest in expected.items():
        path = Path(manifest["variants"][name]["path"])
        require(file_hash(path) == digest, "export pin drift: " + name)
    for k in ("leanchecker","leanchecker-paranoid"):
        require(file_hash(manifest["tools"][k]["path"]) ==
                pins["lean_release_binaries_sha256"][k],
                "official checker version drift: " + k)
    return manifest

def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = preflight(args)
    current_sha = subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=REPO,text=True).strip()
    report = dict(schema="mathgraph.selected-parser-phase-profile.v1",
                  source_git_sha=current_sha, profile=args.profile,
                  repetitions=args.repetitions,
                  status="IN_PROGRESS", run_completed=False,
                  checker_witness_scope="diagnostic actual entire kernel parser and selected checker",
                  host=dict(name=platform.node(), architecture=platform.machine(),
                            system=platform.system()),
                  binary_sha256={
                      n:file_hash(getattr(args,n)) for n in (
                          "profiled_checker","selected_checker","indexer","full_checker")},
                  tools={}, negative_controls={}, edits={}, comparisons={},
                  source_sha256={
                      p:file_hash(REPO/p) for p in (
                          "experiments/incremental/profile_selected_parser.py",
                          "src/bin/check_selected_profiled.rs",
                          "src/bin/check_selected.rs",
                          "src/parser.rs", "src/tc.rs")})
    write(args.out / "summary.json",report)
    baseline, bref = fresh_index(
        Path(manifest["variants"]["baseline"]["path"]),
        args.indexer, args.out / "original-reference" / "baseline")
    require(baseline["count"]==EXPECTED[args.profile]["baseline"],
            "original obligation count changed")
    refs={}
    for variant in VARIANTS:
        vpath = Path(manifest["variants"][variant]["path"])
        idx,index_proc=fresh_index(
            vpath,args.indexer,args.out/"original-reference"/variant)
        require(index_proc["returncode"]==0 and
                idx["count"]==baseline["count"], "qualified index layout changed")
        # Exactly the finite tested conservative dependency predicate, against
        # a pinned trusted baseline and identical toolchain environment.
        checked,reused=independent_partition(baseline,idx)
        require(len(checked)==EXPECTED[args.profile][variant],
                "selected cone differs from frozen workload expectation")
        require(len(reused)+len(checked)==idx["count"],
                "not a complete obligation partition")
        refs[variant]=dict(export=str(vpath),checked_indices=checked,
                           reused_count=len(reused),obligations=idx["count"])
        directory=args.out/variant
        directory.mkdir(parents=True,exist_ok=True)
        config=directory/"config.json"
        chosen=directory/"selected.json"
        write(config,configuration(vpath))
        write(chosen,checked)
        phases=[]
        for rep in range(args.repetitions):
            order=("original","profiled") if (rep+(variant=="unrelated-definition"))%2==0 \
                else ("profiled","original")
            rows={}
            for mode in order:
                binary=args.profiled_checker if mode=="profiled" else args.selected_checker
                rec,stdout=timed_checker(
                    binary,config,chosen,directory/str(rep)/mode)
                require(not rec["timed_out"] and rec["returncode"]==0,
                        "actual Rust selected checker refused valid export: " + mode)
                response=exact_contract(stdout,len(checked),idx["count"],
                                        mode=="profiled")
                rows[mode]=dict(response=response,wall_seconds=rec["wall_seconds"],
                                child_cpu_seconds=rec["completed_child_cpu_seconds"])
            require(rows["original"]["response"]["checked"] ==
                    rows["profiled"]["response"]["checked"],
                    "profiled and original selected checker disagree")
            phases.append(dict(repetition=rep,execution_order=list(order),
                               actual=rows))
            report["edits"][variant]=dict(source=refs[variant],
                complete=False,rows=phases)
            write(args.out/"summary.json",report)
        # Independent full Rust and C++/paranoid oracles on the identical
        # actual genuine edited source, not a synthetic index/proof.
        original_config=directory/"config.json"
        oracles = {}
        for name,command in [
            ("rust",[args.full_checker,original_config]),
            ("leanchecker",[manifest["tools"]["leanchecker"]["path"],
                            "--from-export",vpath]),
            ("leanchecker-paranoid",[manifest["tools"]["leanchecker-paranoid"]["path"],
                                     "--from-export",vpath])
        ]:
            rec,_=command_run(command,directory/"fresh-oracles"/name,timeout=180)
            require(not rec["timed_out"] and rec["returncode"]==0,
                    "independent full checker rejected valid edited export: "+name)
            oracles[name]=dict(exitcode=rec["returncode"],
                               wall_seconds=rec["wall_seconds"])
        intrinsic=[v["actual"]["profiled"]["response"] for v in phases]
        parse_median=statistics.median(v["parse_seconds"] for v in intrinsic)
        selected_median=statistics.median(v["selected_check_seconds"] for v in intrinsic)
        total_median=statistics.median(v["total_seconds"] for v in intrinsic)
        complete_median=statistics.median(
            v["actual"]["profiled"]["wall_seconds"] for v in phases)
        report["edits"][variant]=dict(
            source=refs[variant],complete=True,rows=phases,oracles=oracles,
            medians=dict(parse_seconds=parse_median,
                         actual_selected_check_seconds=selected_median,
                         intrinsic_total_seconds=total_median,
                         profiled_complete_command_seconds=complete_median,
                         original_complete_command_seconds=statistics.median(
                             v["actual"]["original"]["wall_seconds"] for v in phases),
                         parse_fraction_of_profiled_intrinsic_total=parse_median/total_median))
        write(args.out/"summary.json",report)

    # Parser completeness is independently falsified: no selected obligations
    # may conceal unused malformed changed DAG nodes.
    for kind in (NEGATIVES if args.profile == 'original' else ()):
        path=Path(manifest["variants"][kind]["path"])
        directory=args.out/"negative-controls"/kind
        directory.mkdir(parents=True,exist_ok=True)
        cfg=directory/"config.json"
        selected=directory/"selected.json"
        write(cfg,configuration(path))
        indices=[]
        if kind=="invalid-proof":
            leaf=next((d["index"] for d in baseline["declarations"]
                       if d["name"]=="IncrementalWorkload.leaf"),None)
            require(type(leaf) is int,"no independently named invalid theorem")
            indices=[leaf]
        write(selected,indices)
        result={}
        for mode in ("original","profiled"):
            binary=args.selected_checker if mode=="original" else args.profiled_checker
            rec,_=timed_checker(binary,cfg,selected,directory/mode)
            require(not rec["timed_out"] and rec["returncode"]==1,
                    "genuine parser/kernel accepted protected negative: "+kind+" / "+mode)
            result[mode]=dict(returncode=rec["returncode"], selected=indices)
        report["negative_controls"][kind]=result
        write(args.out/"summary.json",report)
    for p,expected in report["source_sha256"].items():
        require(file_hash(REPO/p)==expected,
                "source bytes changed during exact-source qualification")
    for name,expected in report["binary_sha256"].items():
        require(file_hash(getattr(args,name))==expected,
                "binary drift during measurement")
    report["status"]="PASS"
    report["run_completed"]=True
    write(args.out/"summary.json",report)
    lines=["# Independent Rust full export parser + selected checking: measured phase boundary",
           "",
           "Exact pinned genuine Lean/Std exports. All phases include complete parser and real selected kernel.",
           "Original Rust selected checker and fresh full Rust/C++/paranoid accepted valid inputs.",
           "Malformed unused changed DAG nodes with zero checked obligations still rejected by the real parser.",
           "",
           "| Source / edit | Obligations checked | Parser phase | Selected checking | Parser fraction | Complete command |",
           "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for variant in VARIANTS:
        row=report["edits"][variant]
        m=row["medians"]
        lines.append(
            f"| {args.profile} / {variant} | {len(row['source']['checked_indices'])} | "
            f"{m['parse_seconds']:.6f}s | {m['actual_selected_check_seconds']:.6f}s | "
            f"{m['parse_fraction_of_profiled_intrinsic_total']*100:.2f}% | "
            f"{m['profiled_complete_command_seconds']:.6f}s |")
    lines+=["", "This diagnostic does NOT reuse the parser, independently authenticate a new producer,"
            " or establish a warm-session speedup. Exact acceptance still requires the previously"
            " verified HMAC/producer/reuse bridge and actual native kernel. The reported ratio is"
            " between instrumentation phases of a separate profiled binary, not a production"
            " code-path speedup.", ""]
    (args.out/"summary.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ("workloads","profiled-checker","selected-checker","indexer",
              "full-checker","out"):
        ap.add_argument("--"+n,required=True,type=Path)
    ap.add_argument("--profile",choices=("original","expanded"),required=True)
    ap.add_argument("--repetitions",type=int,default=5)
    args=ap.parse_args()
    if args.repetitions!=5:
        ap.error("prespecified independent phase test requires 5 complete paired repetitions")
    for name in ("workloads","profiled_checker","selected_checker","indexer",
                 "full_checker","out"):
        setattr(args,name,getattr(args,name).resolve())
    return run(args)

if __name__=="__main__":
    sys.exit(main())
