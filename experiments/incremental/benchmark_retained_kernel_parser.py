#!/usr/bin/env python3
"""Bounded shadow test: retained REAL Rust parser vs full fresh Rust parser.

No new accepted receipt is issued by the retained parser. The original
source-owning Lean producer, HMAC transition admission, full Rust selected
checker and existing sparse signed receipt qualify source and applicability.
The retained Rust parser separately checks every changed DAG row and the same
selected obligations; independent full-index and Rust/C++/paranoid checks are
oracles. Baseline parsing/session startup are charged separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

from build_workloads import EDITS
from producer_delta import DeltaSession, JsonProcess
from qualify_delta import (configuration, file_hash, fresh_index,
                           audit_partition, audit_receipt, command_run,
                           sealed_snapshot, write, NAMES)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VARIANTS = ("early-definition", "unrelated-definition")
EXPECTED = {
    "original": {"early-definition": (413, 3023),
                 "unrelated-definition": (1,3435)},
    "expanded": {"early-definition": (672, 10981),
                 "unrelated-definition": (260, 11393)},
}

def require(ok,message):
    if not ok:raise ValueError(message)

def runner_start(session,binary,log):
    root=Path(log)
    root.mkdir(parents=True,exist_ok=True)
    baseline_config=session.temp/"index-config.json"
    require(baseline_config.is_file(),"missing exact parsed source config")
    time_start=time.perf_counter()
    proc=JsonProcess(
        [str(binary),str(baseline_config),session.old['export_sha256']],
        root/"retained-rust.stderr",timeout=120)
    response=proc.receive()
    elapsed=time.perf_counter()-time_start
    require(response.get('status')=='ready' and
            response.get('baseline_sha256')==session.old['export_sha256'] and
            response.get('total_declarations')==session.old['index']['count'],
            "parsed baseline differs from HMAC-verified Lean source")
    return proc,dict(launch_and_parse_seconds=elapsed,
                     native_parser_seconds=response['baseline_parse_seconds'])

def actual_acceptance(session,result,original_index,current_index,authority_key,export,indexer,where):
    require(result.get('status')=='VERIFIED' and result.get('evidence_id'),
            "source-owned accepted delta was not warranted")
    require(result['checker_result']['code']==0,
            "existing selected Rust checker refused source-owned delta")
    snapshot=Path(session.snapshot_path)
    seals=sealed_snapshot(snapshot)
    require(seals['sha256']==result['export_sha256'],"not the actual sealed changed source")
    index,proc=fresh_index(snapshot,indexer,Path(where)/"fresh-index")
    require(proc['returncode']==0 and
            json.dumps(index,sort_keys=True)==json.dumps(current_index,sort_keys=True),
            "retained session source disagrees with independently pinned full index")
    partition=audit_partition(result,original_index,index)
    audit=audit_receipt(session.root,result,index,authority_key.read_bytes())
    require(audit['issuer_hmac_valid'] and audit['all_content_addresses_valid'],
            "HMAC and delta content address audit failed")
    return partition

def prepare_profile(args,label,workloads):
    manifest=json.loads((workloads/"manifest.json").read_bytes())
    out=args.out/label
    out.mkdir(parents=True)
    references={}
    for variant in ("baseline",)+VARIANTS:
        entry=Path(manifest['variants'][variant]['path'])
        index,rec=fresh_index(entry,args.indexer,out/"reference"/variant)
        require(rec['returncode']==0,"independent genuine Lean index failed")
        references[variant]=index
    return manifest,references

def retained_request(delta,chosen,names,path,good_hash=True):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=True)
    dpath=path/"changed.ndjson"
    ipath=path/"indices.json"
    dpath.write_bytes(delta)
    write(ipath,chosen)
    return dict(delta_path=str(dpath),
                delta_sha256=(hashlib.sha256(delta).hexdigest()
                              if good_hash else '0'*64),
                selected_indices_path=str(ipath),
                expected_changed_names=list(names))

def paired_valid(args,label,workloads,manifest,references,report):
    out=args.out/label
    for variant in VARIANTS:
        report["profiles"][label][variant]=dict(samples=[],complete=False)
        for rep in range(args.repetitions):
            directory=out/"samples"/variant/str(rep)
            directory.mkdir(parents=True)
            # Every sample has a genuinely re-elaborated Lean source-owned delta,
            # independently HMAC admitted baseline and selected-kernel receipt.
            session=DeltaSession(
                root=directory/"session",workloads=workloads,
                producer=args.producer,checker=args.selected_checker,
                indexer=args.indexer,index_session=args.index_session,
                authority_key=args.authority_key,sparse_index_wire=True,
                sparse_receipt=True,frozen_baseline=True)
            shadow=None
            try:
                start=time.perf_counter()
                ready=session.start()
                controller_setup=time.perf_counter()-start
                require(ready['status']=='READY',
                        "source owner did not authenticate accepted initial environment")
                shadow,parsed_setup=runner_start(
                    session,args.retained_checker,directory/"shadow")
                # Source transition from the real pinned Lean producer; only
                # these attested bytes are passed to the retained parser.
                txn=session.prepare(
                    workloads/variant/"source",
                    EDITS[variant],NAMES[variant])
                require(txn['attestation']['payload']['delta_sha256']==
                        hashlib.sha256(txn['delta_bytes']).hexdigest(),
                        "source-owned attestation omitted changed-byte hash")
                result=session.validate_apply(txn)
                partition=actual_acceptance(
                    session,result,references["baseline"],references[variant],
                    args.authority_key,args.full_checker,
                    args.indexer,directory)
                checked=partition['checked_indices']
                expected=EXPECTED[label][variant]
                require((len(checked),len(partition['reused_indices']))==expected,
                        "frozen genuine Lean/Std affected cone changed")
                config=session.temp/"selected-config.json"
                indices=session.temp/"indices.json"
                req=retained_request(
                    txn['delta_bytes'],checked,
                    txn['attestation']['payload']['changed_names'],
                    directory/"shadow-input")
                # A/B order alternates. Full selected checker processes the
                # identical sealed composite from scratch; retained Rust
                # checker processes the original parsed environment plus the
                # authenticated delta. Neither can issue an acceptance receipt.
                modes=("retained","fresh") if (rep+(variant=="unrelated-definition"))%2==0 \
                    else ("fresh","retained")
                trials={}
                for mode in modes:
                    if mode=="fresh":
                        rec,output=command_run(
                            [args.selected_checker,config,indices],
                            directory/"fresh-selected",timeout=180)
                        require(not rec['timed_out'] and rec['returncode']==0,
                                "fresh selected kernel refused genuine Lean source")
                        response=json.loads(output)
                        require(response.get('checked')==len(checked) and
                                response.get('total_declarations')==references[variant]['count'],
                                "fresh selected kernel count mismatch")
                        trials[mode]=dict(wall_seconds=rec['wall_seconds'],
                                          child_cpu_seconds=rec['completed_child_cpu_seconds'],
                                          checked=response['checked'])
                    else:
                        begun=time.perf_counter()
                        response=shadow.request(req)
                        elapsed=time.perf_counter()-begun
                        require(response.get('status')=='checked' and response.get('code')==0 and
                                response.get('kernel')=='sokonanoda_real_selected_declaration_check' and
                                response.get('checked')==len(checked) and
                                response.get('total_declarations')==references[variant]['count'],
                                "real retained Rust parser/selected kernel disagrees with fresh checker")
                        trials[mode]=dict(wall_seconds=elapsed,
                                          delta_parse_and_finish_seconds=response['delta_parse_and_finish_seconds'],
                                          selected_check_seconds=response['selected_check_seconds'],
                                          checked=response['checked'])
                full_oracles={}
                if rep==0:
                    for checker,command in [
                        ('full-rust',[args.full_checker,config]),
                        ('cxx',[manifest['tools']['leanchecker']['path'],
                                "--from-export",session.snapshot_path]),
                        ('paranoid-cxx',[manifest['tools']['leanchecker-paranoid']['path'],
                                         "--from-export",session.snapshot_path])
                    ]:
                        rec,_=command_run(command,directory/"full-oracles"/checker,timeout=180)
                        require(rec['returncode']==0 and not rec['timed_out'],
                                "independent fresh full-kernel oracle declined source: "+checker)
                        full_oracles[checker]=dict(returncode=rec['returncode'],
                                                   wall_seconds=rec['wall_seconds'])
                sample=dict(variant=variant,repetition=rep,
                            actual_kernel_checked=len(checked),
                            reused=len(partition['reused_indices']),
                            baseline_controller_setup_seconds=controller_setup,
                            baseline_native_parser_setup=parsed_setup,
                            source_sha256=result['export_sha256'],
                            original_receipt_id=result['evidence_id'],
                            order=list(modes),trials=trials,full_oracles=full_oracles)
                report["profiles"][label][variant]["samples"].append(sample)
                write(args.out/"summary.json",report)
            finally:
                if shadow is not None:shadow.close()
                session.close()
        samples=report["profiles"][label][variant]["samples"]
        median=lambda arm:statistics.median(x['trials'][arm]['wall_seconds'] for x in samples)
        profile_med=statistics.median(
            x['trials']['retained']['delta_parse_and_finish_seconds'] for x in samples)
        report["profiles"][label][variant].update(
            complete=True,
            medians=dict(fresh_selected_wall_seconds=median("fresh"),
                         retained_selected_wall_seconds=median("retained"),
                         retained_delta_parser_seconds=profile_med,
                         savings=1-median("retained")/median("fresh")))
        write(args.out/"summary.json",report)

def parser_negative(args,label,workloads,refs,report):
    # An invalid unused changed node must be rejected even with ZERO checked
    # obligations. This is a parser-only falsifier; no source HMAC is forged.
    baseline_data=Path(json.loads((workloads/"manifest.json").read_bytes())
                       ['variants']['baseline']['path']).read_bytes()
    parsed=[json.loads(line) for line in baseline_data.splitlines()]
    next_expr=max(row['ie'] for row in parsed if 'ie' in row)+1
    invalid=json.dumps({'ie':next_expr,'bvar':'not-an-integer'},
                       separators=(',',':')).encode()+b'\n'
    overwrite=json.dumps({'ie':2,'sort':0},separators=(',',':')).encode()+b'\n'
    for name,delta,expected_names,selected in [
        ('malformed-unused-node',invalid,[],[]),
        ('overwrite-admitted-expression',overwrite,[],[]),
    ]:
        directory=args.out/label/"negative"/name
        directory.mkdir(parents=True)
        session=DeltaSession(
            root=directory/"session",workloads=workloads,
            producer=args.producer,checker=args.selected_checker,
            indexer=args.indexer,index_session=args.index_session,
            authority_key=args.authority_key,sparse_index_wire=True,
            sparse_receipt=True,frozen_baseline=True)
        shadow=None
        try:
            session.start()
            shadow,_=runner_start(session,args.retained_checker,directory/"shadow")
            req=retained_request(delta,selected,expected_names,directory/"input")
            response=shadow.request(req)
            require(response.get('status')=='rejected' and response.get('code')==1,
                    "retained parser failed to reject unsupported changed DAG bytes")
            report['negative_controls'][label+"-"+name]=dict(
                passed=True,reason=response.get('reason'),
                checked=selected,source='parser_only_unsigned_adversarial_bytes')
            write(args.out/"summary.json",report)
        finally:
            if shadow is not None: shadow.close()
            session.close()

def run(args):
    args.out.mkdir(parents=True,exist_ok=False)
    source_sha=subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=REPO,text=True).strip()
    report=dict(schema="mathgraph.retained-genuine-kernel-parser-shadow.v1",
                source_sha=source_sha,scope="one authenticated baseline and one source-owned simple delta; low-level oracle comparison only",
                full_kernel_receipt="original previously qualified source-owned selected Rust checker",
                timing_boundary="source-owner baseline parse/setup separately charged; compare native checker phases over same exact sealed input",
                profile_count=2,repetitions=args.repetitions,complete=False,
                source_hashes={},binary_hashes={},negative_controls={},
                profiles={"original":{},"expanded":{}})
    for path in ("src/parser.rs","src/bin/check_selected_retained_session.rs",
                 "src/bin/check_selected.rs",
                 "experiments/incremental/benchmark_retained_kernel_parser.py",
                 "experiments/incremental/producer_delta.py"):
        report["source_hashes"][path]=file_hash(REPO/path)
    for binary in ('retained_checker','selected_checker','indexer',
                   'index_session','full_checker','producer'):
        report["binary_hashes"][binary]=file_hash(getattr(args,binary))
    write(args.out/"summary.json",report)
    for label,workloads in (("original",args.original_workloads),
                            ("expanded",args.expanded_workloads)):
        manifest,references=prepare_profile(args,label,workloads)
        paired_valid(args,label,workloads,manifest,references,report)
        parser_negative(args,label,workloads,references,report)
    for p,sha in report["source_hashes"].items():
        require(file_hash(REPO/p)==sha,"measured source bytes changed")
    for p,sha in report["binary_hashes"].items():
        require(file_hash(getattr(args,p))==sha,"checker provenance changed")
    report["complete"]=True
    write(args.out/"summary.json",report)
    lines=["# One-shot retained native Rust parser: shadow low-level experiment",
           "","This reports parser/kernal phase economics, NOT a new accepted receipt or full producer-to-durable lifecycle speedup.",
           "Baseline parsed once on session startup (charged separately). Each compared changed export uses genuine source-owned Lean data.",
           "Original full Rust selected checker and fresh Rust/C++/paranoid full oracles remain acceptance authorities.","",
           "| Workload / edit | Fresh selected checker | Retained parsed-state checker | Median savings | Delta parse+finish |",
           "| --- | ---: | ---: | ---: | ---: |"]
    for label in ("original","expanded"):
        for variant in VARIANTS:
            m=report["profiles"][label][variant]["medians"]
            lines.append(f"| {label} / {variant} | {m['fresh_selected_wall_seconds']:.6f}s | "
                         f"{m['retained_selected_wall_seconds']:.6f}s | "
                         f"{100*m['savings']:.2f}% | {m['retained_delta_parser_seconds']:.6f}s |")
    lines+=["","Same-kernel parity on accepted real source, genuine typed full-index oracle,"
            " protected malformed/overwrite delta parser refusals required.",
            "New retained parser executable semantics are not machine-proven."
            " The producer, attestation and HMAC policy are also outside the kernel proof.",
            "Cold startup, arbitrary Lean declarations/topology and true end-to-end"
            " change-proportional checking remain UNKNOWN."]
    (args.out/"summary.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original-workloads','expanded-workloads','producer','selected-checker',
                 'retained-checker','indexer','index-session','full-checker','authority-key','out'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--repetitions',type=int,default=5)
    args=p.parse_args()
    if args.repetitions!=5:
        p.error('qualified shadow probe requires exactly five paired examples per edit')
    for name in ('original_workloads','expanded_workloads','producer','selected_checker',
                 'retained_checker','indexer','index_session','full_checker','authority_key','out'):
        setattr(args,name,getattr(args,name).resolve())
    return run(args)

if __name__=='__main__':
    sys.exit(main())
