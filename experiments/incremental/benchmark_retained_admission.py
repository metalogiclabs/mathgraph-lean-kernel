#!/usr/bin/env python3
"""Exact-source production-adapter qualification of one-shot retained native Rust kernel.

Two distinct economic/qualification phases:
- qualify: run *all* original and expanded source-owned positive, negative,
  receipt, cold-restart, provenance and independent full Rust/C++/paranoid
  gates using the retained kernel as the actual accepted checker.
- compare: paired warm producer→HMAC→identity→sealed materialization→genuine
  kernel→signed sparse receipt against the unchanged accepted full-parser path.

The new Rust binary is an added signed-provenance trust dependency. It is never
allowed to approve a source change without issuer-authenticated producer bytes
and the original conservative reuse predicate.
"""
import argparse
import hashlib
import json
import random
import statistics
import subprocess
from pathlib import Path

from producer_delta import DeltaSession, SPARSE_ACCEPTANCE
from qualify_delta import Qualification, paired_economics, canonical, file_hash, write

MODES=("fresh_selected","retained_selected")
VARIANTS=("early-definition","unrelated-definition")
COMPONENTS=(
    "src/parser.rs","src/bin/check_selected_retained_session.rs",
    "src/bin/check_selected.rs","experiments/incremental/producer_delta.py",
    "experiments/incremental/qualify_delta.py",
    "experiments/incremental/benchmark_retained_admission.py"
)

def require(x,msg):
    if not x:raise ValueError(msg)

def session_type(native):
    class ActualAcceptedSession(DeltaSession):
        def __init__(self,*a,**k):
            super().__init__(
                *a,**k,retained_checker=native,
                sparse_index_wire=True,sparse_receipt=True,
                frozen_baseline=True)
    return ActualAcceptedSession

def qualifier(args,workloads,profile,mode,scope):
    binary=(args.retained_checker if mode=="retained_selected" else None)
    q=Qualification(argparse.Namespace(
        workloads=workloads,producer=args.producer,checker=args.checker,
        indexer=args.indexer,index_session=args.index_session,
        full_checker=args.full_checker,authority_key=args.authority_key,
        out=args.out/profile/scope/mode,repetitions=args.repetitions))
    q.session_type=session_type(binary)
    # Extend the existing locked test authority rather than editing any
    # original qualification predicates. HMAC evidence also embeds this SHA.
    original_preflight=q.preflight
    def preflight():
        original_preflight()
        if binary is not None:
            q.report["tools"]["retained_checker"]={
                "path":str(binary),"sha256":file_hash(binary)}
            q.report["measured_source_sha256"]["src/bin/check_selected_retained_session.rs"] = (
                file_hash(Path(__file__).resolve().parents[2] /
                          "src/bin/check_selected_retained_session.rs"))
        q.report["measured_source_sha256"]["experiments/incremental/benchmark_retained_admission.py"] = (
            file_hash(Path(__file__)))
        q.flush()
    q.preflight=preflight
    return q

def verified_result(sample,mode):
    require('error' not in sample and bool(sample.get('partition_audit')) and
            bool(sample.get('persisted_acceptance_audit')),
            "actual HMAC delta or independent full typed identity declined: "+
            str(sample.get('error')))
    source=json.loads(Path(sample['result_path']).read_bytes())
    audit=sample["persisted_acceptance_audit"]
    require(source.get("status")=="VERIFIED" and bool(source.get("evidence_id")),
            "no accepted issuer HMAC receipt")
    require(source.get("checker_result",{}).get("code")==0 and
            sample["direct_rust"]["returncode"]==0,
            "selected or fresh full Rust checker rejected")
    require(audit["issuer_hmac_valid"] and audit["all_content_addresses_valid"] and
            audit["receipt_schema"]==SPARSE_ACCEPTANCE and
            audit["contains_complete_index"] is False,
            "signed sparse receipt or complete fresh index audit disagreed")
    require(source.get("export_sha256")==sample["snapshot"]["sha256"],
            "real sealed checked export hash disagreed")
    if mode=="retained_selected":
        native=source.get("native_kernel_report")
        require(type(native) is dict and native.get("status")=="checked" and
                native.get("kernel")=="sokonanoda_real_selected_declaration_check" and
                native.get("scope")=="selected_obligations_under_caller_trusted_environment" and
                native.get("code")==0 and
                native.get("checked")==source["counts"]["rechecked"] and
                native.get("total_declarations")==source["counts"]["total"],
                "native retained kernel did not actually check the signed obligations")
        require(source["producer_provenance"].get("selected_kernel_backend")==
                "sha-pinned-retained-parser-v1",
                "retained parser binary missing from HMAC provenance")
        require("retained_checker" in source["producer_provenance"]["tools"],
                "retained executable digest missing from HMAC tools")
    else:
        require(source.get("native_kernel_report") is None and
                "retained_checker" not in source["producer_provenance"]["tools"],
                "fresh selected checker path unexpectedly used retained kernel")
    return source,audit

def normalized(result):
    return [dict(name=d["name"],index=d["index"],
                 status=d["status"],reason=d["reason"],
                 dependency_witness=d["dependency_witness"])
            for d in result["decisions"]]

def scenario_samples(q,refs,mode,variant,rep):
    sample=q.sample(variant,rep,refs)
    r,audit=verified_result(sample,mode)
    return dict(
        wall_seconds=sample["apply_wall_seconds"],
        kernel_seconds=r["timings"]["checking_seconds"],
        identity_seconds=r["timings"]["identity_update_seconds"],
        producer_seconds=r["timings"]["producer_seconds"],
        persistence_seconds=r["timings"]["persistence_seconds"],
        setup_seconds=sample["setup_wall_seconds"],
        checked=r["counts"]["rechecked"],reused=r["counts"]["reused"],
        export_sha256=r["export_sha256"],
        decisions_sha256=hashlib.sha256(canonical(normalized(r))).hexdigest(),
        sparse_receipt_bytes=audit["receipt_bytes"],
        policy_tool_sha256=r["producer_provenance"]["tools"],
        kernel_report=r.get("native_kernel_report"),
        cpp_oracles={name:v["returncode"] for name,v in
                     sample.get("independent_kernels",{}).items()},
        receipt_verified=True)

def compare(args):
    args.out.mkdir(parents=True,exist_ok=False)
    source_sha=subprocess.check_output(
        ["git","rev-parse","HEAD"],text=True).strip()
    report=dict(schema="mathgraph.retained-kernel-issuer-accepted-ab.v1",
                source_sha=source_sha,
                scope="full source-owner HMAC policy and actual accepted retained selected Rust kernel",
                qualified=False,completed=False,
                limits=["Frozen original/expanded source-only universe.",
                        "One baseline-anchored edit per actual Rust parser instance.",
                        "Warm source→signed persistence timed; cold seed separately charged.",
                        "Trusted new retained Rust parser bridge not formally proved."],
                source_sha256={p:file_hash(Path(p)) for p in COMPONENTS},
                binary_sha256={n:file_hash(getattr(args,n)) for n in
                  ("producer","checker","retained_checker","indexer","index_session","full_checker")},
                profiles={})
    write(args.out/"summary.json",report)
    for profile,workloads in (("original",args.original_workloads),
                              ("expanded",args.expanded_workloads)):
        q={mode:qualifier(args,workloads,profile,mode,"comparison") for mode in MODES}
        refs={}
        for mode in MODES:
            q[mode].preflight()
            refs[mode]={v:q[mode].reference(v)
                        for v in ("baseline",)+VARIANTS}
        require(canonical(refs[MODES[0]])==canonical(refs[MODES[1]]),
                "accepted verifier arms differ on full independently pinned typed indices")
        out={v:[] for v in VARIANTS}
        report["profiles"][profile]={}
        first_retained_early=None
        for rep in range(args.repetitions):
            variant_order=list(VARIANTS)
            random.Random(20261017+rep).shuffle(variant_order)
            for variant in variant_order:
                modes=MODES if (rep+(variant=="unrelated-definition"))%2==0 else MODES[::-1]
                pair=dict(repetition=rep,order=list(modes),variant=variant,arms={})
                for mode in modes:
                    qmode=q[mode]
                    sample=qmode.sample(variant,rep,refs[mode])
                    outcome,acceptance=verified_result(sample,mode)
                    if variant=="early-definition" and rep==0 and mode=="retained_selected":
                        first_retained_early=sample
                    arm=dict(
                        wall_seconds=sample["apply_wall_seconds"],
                        kernel_seconds=outcome["timings"]["checking_seconds"],
                        identity_seconds=outcome["timings"]["identity_update_seconds"],
                        producer_seconds=outcome["timings"]["producer_seconds"],
                        persistence_seconds=outcome["timings"]["persistence_seconds"],
                        setup_seconds=sample["setup_wall_seconds"],
                        checked=outcome["counts"]["rechecked"],reused=outcome["counts"]["reused"],
                        export_sha256=outcome["export_sha256"],
                        decisions_sha256=hashlib.sha256(canonical(normalized(outcome))).hexdigest(),
                        sparse_receipt_bytes=acceptance["receipt_bytes"],
                        kernel_report=outcome.get("native_kernel_report"),
                        cpp_oracles={name:v["returncode"] for name,v in
                                     sample.get("independent_kernels",{}).items()})
                    pair["arms"][mode]=arm
                for key in ("checked","reused","export_sha256","decisions_sha256"):
                    require(pair["arms"][MODES[0]][key]==pair["arms"][MODES[1]][key],
                            "accepted native kernel differed from original signed outcomes: "+key)
                if rep==0:
                    for mode in MODES:
                        require(pair["arms"][mode]["cpp_oracles"]==
                                {"leanchecker":0,"leanchecker-paranoid":0},
                                "independent official/paranoid full checker discrepancy")
                out[variant].append(pair)
                report["profiles"][profile][variant]=dict(pairs=out[variant],complete=False)
                write(args.out/"summary.json",report)
        require(first_retained_early is not None,"no retained native accepted restart witness")
        replay=q["retained_selected"].sample(
            "early-definition","cold-restart",refs["retained_selected"],
            cold_root=Path(first_retained_early["result_path"]).parent/"session",
            replay_id=first_retained_early["evidence_id"])
        fresh_result,_audit=verified_result(replay,"retained_selected")
        old=json.loads(Path(first_retained_early["result_path"]).read_bytes())
        require(fresh_result["export_sha256"]==old["export_sha256"] and
                normalized(fresh_result)==normalized(old),
                "cold restart retained native accepted decision changed")
        report["profiles"][profile]["cold_restart"]=dict(
            passed=True,evidence_id=old["evidence_id"],
            source_sha256=old["export_sha256"])
        for mode in MODES:
            qmode=q[mode]
            qmode.report["run_completed"]=True
            qmode.flush()
            require(qmode.report["correctness_passed"],
                    "source owner, verifier, or full oracle A/B admission failed")
        for variant in VARIANTS:
            pairs=out[variant]
            require(len(pairs)==args.repetitions and args.repetitions>=5,
                    "incomplete A/B pairs")
            economics=paired_economics([
                dict(apply_wall_seconds=x["arms"]["retained_selected"]["wall_seconds"],
                     direct_wall_seconds=x["arms"]["fresh_selected"]["wall_seconds"])
                for x in pairs],seed=20261017)
            kernel=paired_economics([
                dict(apply_wall_seconds=x["arms"]["retained_selected"]["kernel_seconds"],
                     direct_wall_seconds=x["arms"]["fresh_selected"]["kernel_seconds"])
                for x in pairs],seed=20261027)
            report["profiles"][profile][variant]=dict(
                pairs=pairs,complete=True,
                warm_economics=economics,selected_kernel_economics=kernel,
                median_startup_s={
                    mode:statistics.median(x["arms"][mode]["setup_seconds"] for x in pairs)
                    for mode in MODES})
        write(args.out/"summary.json",report)
    for path,h in report["source_sha256"].items():
        require(file_hash(Path(path))==h,"source drift during paired A/B")
    for name,h in report["binary_sha256"].items():
        require(file_hash(getattr(args,name))==h,"signed executable drift during paired A/B")
    report["qualified"]=report["completed"]=True
    write(args.out/"summary.json",report)
    lines=["# Real HMAC-accepted retained parsed Rust kernel versus original accepted selected checker",
           "", "One source-owned Lean producer and identical HMAC policy, conservative reuse and signed sparse receipts.",
           "Full independent native/Python typed-index parity, Rust/C++/paranoid acceptance and protected cold replay.",
           "Retained Rust binary is a NEW pinned-provenance trust dependency; no unproved kernel-bridge equivalence is claimed.",
           "Warm producer→authentication→identity→full sealed source→kernel→signed persistence timed; initial setup excluded.",
           "",
           "| Source / edit | Original accepted warm (s) | Retained-native accepted warm (s) | Saving | Wins | Bootstrap 95% ratio | Gate |",
           "| --- | ---: | ---: | ---: | ---: | --- | --- |"]
    for profile in ("original","expanded"):
        for variant in VARIANTS:
            e=report["profiles"][profile][variant]["warm_economics"]
            ci=e["bootstrap_ratio_interval_95"]
            lines.append(
                f"| {profile} / {variant} | {e['direct_median_wall_seconds']:.6f} | "
                f"{e['apply_median_wall_seconds']:.6f} | "
                f"{(1-e['median_ratio'])*100:.2f}% | {e['paired_wins']}/{e['paired_count']} | "
                f"[{ci[0]:.5f},{ci[1]:.5f}] | {e['status']} |")
    lines += ["", "Original complete-index HMAC baseline and selected checker remain qualified separately;",
              "unknown producer/kernel representation bridge validity outside frozen bounded tests;",
              "whole export materialization/hash, cold startup and multi-update lifetime remain unqualified."]
    (args.out/"summary.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    return report

def qualification(args):
    args.out.mkdir(parents=True,exist_ok=False)
    results={}
    for profile,workloads in (("original",args.original_workloads),
                              ("expanded",args.expanded_workloads)):
        q=qualifier(args,workloads,profile,"retained_selected","protected-matrix")
        report=q.run()
        if not report["correctness_passed"]:
            raise ValueError("protected original real-source qualification failed: "+profile)
        results[profile]=dict(qualification_status=report["qualification_status"],
                              required_gates=sum(g["required"] for g in report["gates"]),
                              failed_gates=[g["name"] for g in report["gates"]
                                            if g["required"] and not g["passed"]],
                              source_sha=report["source_git_commit"],
                              retained_kernel_tool_sha256=report["tools"]["retained_checker"]["sha256"],
                              actual_samples=len(report["samples"]),
                              signed_kernel_backend="sha-pinned-retained-parser-v1")
    write(args.out/"protected-summary.json",dict(
        schema="mathgraph.retained-native-kernel-protected-v1",
        qualified=True,profiles=results,
        source_sha=subprocess.check_output(
            ["git","rev-parse","HEAD"],text=True).strip()))
    return results

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("protected","compare"),required=True)
    for flag in ("original-workloads","expanded-workloads","producer",
                 "checker","retained-checker","indexer","index-session",
                 "full-checker","authority-key","out"):
        p.add_argument("--"+flag,required=True,type=Path)
    p.add_argument("--repetitions",type=int,default=5)
    args=p.parse_args()
    require(args.repetitions==5,"five paired qualification repeats required")
    for name in ("original_workloads","expanded_workloads","producer",
                 "checker","retained_checker","indexer","index_session",
                 "full_checker","authority_key","out"):
        setattr(args,name,getattr(args,name).resolve())
    return qualification(args) if args.mode=="protected" else compare(args)

if __name__=="__main__":
    main()
