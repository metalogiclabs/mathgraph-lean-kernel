#!/usr/bin/env python3
"""Exact-source production-adapter qualification of one-shot retained native Rust kernel.

Three qualification/comparison modes:
- protected: run *all* original and expanded source-owned positive, negative,
  receipt, cold-restart, provenance and independent full Rust/C++/paranoid
  gates using the retained kernel as the actual accepted checker.
- receipt-compare: same retained checker and authority policy, comparing canonical
  JSON equality against shared-baseline JSON equality, preserving phase evidence.
- compare: paired warm producer→HMAC→identity→sealed materialization→genuine
  kernel→signed sparse receipt against the unchanged accepted full-parser path.

The new Rust binary is an added signed-provenance trust dependency. It is never
allowed to approve a source change without issuer-authenticated producer bytes
and the original conservative reuse predicate.
"""
import argparse
import hashlib
import gzip
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import unittest
from pathlib import Path

from producer_delta import DeltaSession, SPARSE_ACCEPTANCE
from qualify_delta import Qualification, paired_economics, canonical, file_hash, write

MODES=("fresh_selected","retained_selected")
RECEIPT_MODES=("canonical_json","shared_json")
VARIANTS=("early-definition","unrelated-definition")
COMPONENTS=(
    "src/identity.rs","src/parser.rs","src/bin/index_session.rs",
    "src/bin/check_selected_retained_session.rs",
    "src/bin/check_selected.rs","experiments/incremental/producer_delta.py",
    "experiments/incremental/qualify_delta.py","experiments/incremental/engine.py",
    "experiments/incremental/test_index_json_equality.py",
    "experiments/incremental/benchmark_retained_admission.py",
    ".github/workflows/incremental-receipt-comparison.yml"
)

def mode_policy(mode):
    if mode in RECEIPT_MODES:
        return dict(retained=True,receipt_comparison=mode)
    if mode in MODES:
        return dict(retained=mode=="retained_selected",receipt_comparison=None)
    raise ValueError("unsupported comparison arm: "+str(mode))

def phase_evidence(result):
    fields=('timings','memory','counts','representation','producer_report','typed_update')
    for field in fields:
        require(type(result.get(field)) is dict,"missing actual phase evidence: "+field)
    for field in ('end_to_end_seconds','end_to_end_cpu_seconds'):
        require(field in result['timings'],"missing complete API phase: "+field)
    for field,value in result['timings'].items():
        if field.endswith('_seconds'):
            require(type(value) in (int,float) and math.isfinite(value) and value>=0,
                    "invalid actual phase duration: "+field)
    return dict({field:result[field] for field in fields},
                native_kernel_report=result.get('native_kernel_report'))

def scoped_economics(pairs,*,seed,scope,metric,candidate,control,includes_setup=False):
    result=paired_economics(pairs,seed=seed)
    result.update(scope=scope,measurement=metric,candidate_arm=candidate,control_arm=control,
                  setup_in_timed_update=includes_setup)
    return result

def self_test():
    class ReceiptComparisonContracts(unittest.TestCase):
        def test_receipt_arms_share_retained_kernel_and_only_change_comparison(self):
            for mode in ('canonical_json','shared_json'):
                self.assertEqual(mode_policy(mode),dict(retained=True,receipt_comparison=mode))
            self.assertEqual(mode_policy('fresh_selected'),dict(retained=False,receipt_comparison=None))
            self.assertEqual(mode_policy('retained_selected'),dict(retained=True,receipt_comparison=None))
            with self.assertRaises(ValueError):mode_policy('unrecognized')

        def test_raw_phase_cpu_memory_and_typed_witness_are_preserved(self):
            value=dict(timings={'end_to_end_seconds':1.0,'end_to_end_cpu_seconds':.9},
                memory={'identity':{'processes':{'retained_kernel':{}}}}, counts={'total':3},
                representation={'immutable_memfd':True},producer_report={'changed_names':['a']},
                typed_update={'index_wire':'baseline_patch_v1'},native_kernel_report={'checked':1})
            self.assertEqual(phase_evidence(value),value)

        def test_comparator_scope_does_not_inherit_fresh_rust_or_wall_labels(self):
            value=scoped_economics([dict(apply_wall_seconds=1.0,direct_wall_seconds=2.0)]*5,
                seed=1,scope='receipt CPU',metric='cpu_seconds',candidate='shared_json',control='canonical_json')
            self.assertEqual(value['scope'],'receipt CPU')
            self.assertEqual(value['measurement'],'cpu_seconds')
            self.assertEqual(value['candidate_arm'],'shared_json')
            self.assertEqual(value['control_arm'],'canonical_json')

        def test_missing_or_nonfinite_phase_evidence_fails_closed(self):
            for value in ({}, {'timings':{'end_to_end_seconds':float('nan')}}):
                with self.assertRaises(ValueError):phase_evidence(value)

    return unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptComparisonContracts)).wasSuccessful()

def require(x,msg):
    if not x:raise ValueError(msg)

def session_type(native,receipt_comparison=None):
    class ActualAcceptedSession(DeltaSession):
        def __init__(self,*a,**k):
            if receipt_comparison is not None:
                k['receipt_index_comparison']=receipt_comparison
            super().__init__(
                *a,**k,retained_checker=native,
                sparse_index_wire=True,sparse_receipt=True,
                frozen_baseline=True)
    return ActualAcceptedSession

def qualifier(args,workloads,profile,mode,scope):
    policy=mode_policy(mode)
    binary=(args.retained_checker if policy['retained'] else None)
    q=Qualification(argparse.Namespace(
        workloads=workloads,producer=args.producer,checker=args.checker,
        indexer=args.indexer,index_session=args.index_session,
        full_checker=args.full_checker,authority_key=args.authority_key,
        out=args.out/profile/scope/mode,repetitions=args.repetitions))
    q.session_type=session_type(binary,policy['receipt_comparison'])
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
    if mode_policy(mode)['retained']:
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
        if mode in RECEIPT_MODES:
            require(source['producer_provenance'].get('receipt_index_comparison')==mode,
                    'receipt comparison mode missing from signed policy')
    else:
        require(source.get("native_kernel_report") is None and
                "retained_checker" not in source["producer_provenance"]["tools"],
                "fresh selected checker path unexpectedly used retained kernel")
    return source,audit

def actual_arm(sample,result,audit,session_root=None):
    """Keep real CPU/memory/phase data and bind every raw acceptance artifact."""
    root=Path(session_root) if session_root is not None else Path(sample['result_path']).parent/'session'
    receipt=root/'cache/records'/(result['evidence_id']+'.json')
    require(receipt.is_file() and file_hash(receipt)==result['evidence_id'],
            'actual signed acceptance record missing or corrupt')
    return dict(
        wall_seconds=sample['apply_wall_seconds'],
        kernel_seconds=result['timings']['checking_seconds'],
        identity_seconds=result['timings']['identity_update_seconds'],
        producer_seconds=result['timings']['producer_seconds'],
        persistence_seconds=result['timings']['persistence_seconds'],
        setup_seconds=sample['setup_wall_seconds'],
        setup_report=sample['setup_report'],
        constructor_seconds=sample['session_constructor_wall_seconds'],
        start_seconds=sample['start_wall_seconds'],
        setup_plus_apply_component_sum_seconds=sample['setup_wall_seconds']+sample['apply_wall_seconds'],
        lifecycle_scope='Observed setup plus apply components for one supported update; shutdown and harness oracles are excluded, no multi-update amortization.',
        checked=result['counts']['rechecked'],reused=result['counts']['reused'],
        export_sha256=result['export_sha256'],snapshot=sample['snapshot'],
        decisions_sha256=hashlib.sha256(canonical(normalized(result))).hexdigest(),
        sparse_receipt_bytes=audit['receipt_bytes'],
        receipt_audit=audit,receipt_path=str(receipt),receipt_sha256=file_hash(receipt),
        result_path=sample['result_path'],result_sha256=file_hash(sample['result_path']),
        baseline_result=sample['baseline_result'],baseline_result_path=sample['baseline_result_path'],
        baseline_result_sha256=sample['baseline_result_sha256'],
        signed_comparison_policy=result['producer_provenance'].get('receipt_index_comparison'),
        policy_tool_sha256=result['producer_provenance']['tools'],
        kernel_report=result.get('native_kernel_report'),direct_rust=sample['direct_rust'],
        full_index_oracle=sample['full_index_oracle'],partition_audit=sample['partition_audit'],
        cpp_oracles={name:v['returncode'] for name,v in sample.get('independent_kernels',{}).items()},
        independent_kernels=sample.get('independent_kernels',{}),
        phases=phase_evidence(result))

def archive_witness(source,destination,role,compress=False):
    source,destination=Path(source),Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if compress:
        with source.open('rb') as src,destination.open('wb') as raw:
            with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:
                shutil.copyfileobj(src,dst)
    else:shutil.copyfile(source,destination)
    record=dict(role=role,path=str(destination),sha256=file_hash(destination),bytes=destination.stat().st_size)
    if compress:record.update(encoding='gzip',uncompressed_sha256=file_hash(source),uncompressed_bytes=source.stat().st_size)
    return record

def preserve_witness(args,profile,variant,mode,sample,result,session_root=None):
    """Representative complete decisions and exact source needed for independent replay.

    Called after the timed sample and all live-input oracles finish. Export/index
    compression is evidence packaging, excluded from every measured API interval.
    """
    root=Path(session_root) if session_root is not None else Path(sample['result_path']).parent/'session'
    out=args.out/'witnesses'/profile/variant/mode
    out.mkdir(parents=True,exist_ok=True)
    receipt=root/'cache/records'/(result['evidence_id']+'.json')
    accepted=json.loads(receipt.read_bytes())['payload']
    representation=root/'cache/representations'/(accepted['delta_representation']+'.json')
    rep=json.loads(representation.read_bytes())
    files=[('result',Path(sample['result_path'])),('accepted_record',receipt),('representation',representation),
           ('delta',root/'cache/deltas'/(rep['delta_sha256']+'.ndjson')),
           ('transition',root/'cache/transitions'/(rep['transition_id']+'.json'))]
    baseline=root/'baseline-cache/records'/(result['previous_evidence']+'.json')
    base_out=args.out/'witnesses'/profile/'baseline'/baseline.name
    base_out.parent.mkdir(parents=True,exist_ok=True)
    if not base_out.exists():shutil.copyfile(baseline,base_out)
    require(file_hash(base_out)==result['previous_evidence'],'baseline witness content address mismatch')
    manifest=[dict(role='baseline_record',path=str(base_out),sha256=file_hash(base_out),bytes=base_out.stat().st_size)]
    # One exact baseline export per profile is sufficient to reconstruct every
    # persistent-ID delta composite. Preserve original bytes via streaming gzip.
    export_out=base_out.parent/'export.ndjson.gz'
    workloads=args.original_workloads if profile=='original' else args.expanded_workloads
    export=Path(json.loads((workloads/'manifest.json').read_bytes())['variants']['baseline']['path'])
    signed_export=json.loads(baseline.read_bytes())['payload']['export_sha256']
    require(file_hash(export)==signed_export,'baseline export witness differs from signed acceptance')
    if not export_out.exists():
        archive_witness(export,export_out,'baseline_export',compress=True)
    manifest.append(dict(role='baseline_export',path=str(export_out),sha256=file_hash(export_out),
        bytes=export_out.stat().st_size,encoding='gzip',uncompressed_sha256=signed_export,
        uncompressed_bytes=export.stat().st_size))
    for role,source in files:
        manifest.append(archive_witness(source,out/(source.parent.name+'-'+source.name),role))
    records=dict(direct_rust=sample['direct_rust'],fresh_native_index=sample['full_index_oracle'],
                 **sample.get('independent_kernels',{}))
    for name,record in records.items():
        if name in ('direct_rust','fresh_native_index'):
            config=Path(record['command'][1])
            require(json.loads(config.read_bytes())['export_file_path']==sample['snapshot']['path'],
                    'archived oracle configuration does not target actual sealed snapshot')
            manifest.append(archive_witness(config,out/(name+'-config.json'),name+'_config'))
        else:
            require(record['command'][1:]==['--from-export',sample['snapshot']['path']],
                    'independent C++ command does not target actual sealed snapshot')
        for stream in ('stdout','stderr'):
            source=Path(record[stream+'_path'])
            compress=name=='fresh_native_index' and stream=='stdout'
            destination=out/(name+'-'+stream+('.log.gz' if compress else '.log'))
            manifest.append(archive_witness(source,destination,name+'_'+stream,compress))
    write(out/'manifest.json',manifest)
    return manifest

def normalized(result):
    return [dict(name=d["name"],index=d["index"],
                 status=d["status"],reason=d["reason"],
                 dependency_witness=d["dependency_witness"])
            for d in result["decisions"]]

def cross_mode_control(qmode,source_mode,target_mode,original):
    root=Path(original['result_path']).parent/'session'
    def records():return {p.name:file_hash(p) for p in sorted((root/'cache/records').glob('*.json'))}
    before=records();session=None;observed=None
    require(bool(before),'cross-mode control has no actual accepted record')
    try:
        session=qmode.new_session(root)
        session.start()
    except ValueError as error:observed=str(error)
    finally:
        if session is not None:session.close()
    after=records()
    passed=observed=='source-owner genesis provenance mismatch' and before==after
    result=dict(passed=passed,source_mode=source_mode,target_mode=target_mode,
        expected_refusal='source-owner genesis provenance mismatch',observed_refusal=observed,
        accepted_records_before=before,accepted_records_after=after,
        scope='Same issuer, source and executable policy; only receipt comparison mode changes during cold reopen.')
    require(passed,'cross-comparison policy failed to refuse without persistence: '+str(result))
    return result

def compare(args,receipt_comparison=False):
    args.out.mkdir(parents=True,exist_ok=False)
    modes=RECEIPT_MODES if receipt_comparison else MODES
    control,candidate=modes
    scope=("Same-source retained-kernel receipt issuance: shared JSON comparison versus canonical JSON comparison."
           if receipt_comparison else
           "Same-source actual accepted retained selected Rust kernel versus fresh selected Rust kernel.")
    source_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    report=dict(schema=("mathgraph.retained-receipt-index-comparison.v1" if receipt_comparison else
                        "mathgraph.retained-kernel-issuer-accepted-ab.v1"),
                source_sha=source_sha,scope=scope,arms=list(modes),control=control,candidate=candidate,
                qualified=False,completed=False,correctness_passed=False,
                measurement_policy=dict(
                    warm="Complete observed apply API; same-source authority and actual selected kernel in both arms.",
                    cold="Constructor/start plus replay recorded separately for one baseline-anchored update.",
                    setup_plus_apply="Observed setup+apply component sum, excludes shutdown and independent oracles; no multi-update amortization.",
                    direct="Fresh full Rust check of the same live sealed memfd, before independent indexing; different comparator from the paired receipt arms.",
                    order="Alternating arms per edit/repetition; deterministic shuffled edit order; warm OS caches are not reset.",
                    memory="Raw procfs phase observations; missing/exited processes remain missing, never interpreted as zero or summed into fake peak RSS."),
                limits=["Frozen original/expanded source-only universe.",
                        "One baseline-anchored edit per actual Rust parser instance.",
                        "Full sealed export materialization, full sparse-record authentication and second conservative reuse pass remain in both arms.",
                        "Trusted retained Rust parser bridge remains a pinned trust dependency."],
                source_sha256={p:file_hash(Path(p)) for p in COMPONENTS},
                binary_sha256={n:file_hash(getattr(args,n)) for n in
                  ("producer","checker","retained_checker","indexer","index_session","full_checker")},
                profiles={})
    def persist():
        write(args.out/"summary.json",report)
        # All actual phase/resource observations remain available without opening N-row decisions.
        write(args.out/"compact-phases.json",dict(schema="mathgraph.receipt-comparison-phases.v1",
            source_sha=source_sha,scope=scope,completed=report['completed'],profiles=report['profiles']))
    persist()
    for profile,workloads in (("original",args.original_workloads),("expanded",args.expanded_workloads)):
        q={mode:qualifier(args,workloads,profile,mode,"comparison") for mode in modes}
        refs={}
        for mode in modes:
            q[mode].preflight()
            if 'host' not in report:report['host']=q[mode].report['host']
            require(report['host']==q[mode].report['host'],'host changed during paired comparison')
            refs[mode]={v:q[mode].reference(v) for v in ("baseline",)+VARIANTS}
        require(canonical(refs[control])==canonical(refs[candidate]),
                "comparison arms differ on full independently pinned typed indices")
        out={v:[] for v in VARIANTS}
        report["profiles"][profile]={}
        first_early={};pending_witnesses=[]
        for rep in range(args.repetitions):
            variant_order=list(VARIANTS)
            random.Random(20261017+rep).shuffle(variant_order)
            for variant in variant_order:
                order=modes if (rep+(variant=="unrelated-definition"))%2==0 else modes[::-1]
                pair=dict(repetition=rep,order=list(order),variant=variant,arms={})
                for mode in order:
                    sample=q[mode].sample(variant,rep,refs[mode])
                    outcome,acceptance=verified_result(sample,mode)
                    if variant=="early-definition" and rep==0:first_early[mode]=sample
                    arm=actual_arm(sample,outcome,acceptance)
                    if rep==0:pending_witnesses.append((variant,mode,sample,arm))
                    pair["arms"][mode]=arm
                for key in ("checked","reused","export_sha256","decisions_sha256"):
                    require(pair["arms"][control][key]==pair["arms"][candidate][key],
                            "signed checker outcomes or dependency witnesses differ: "+key)
                if receipt_comparison:
                    require(pair['arms'][control]['policy_tool_sha256']==pair['arms'][candidate]['policy_tool_sha256'],
                            'receipt comparison arms used different pinned executables')
                if rep==0:
                    for mode in modes:
                        require(pair["arms"][mode]["cpp_oracles"]==
                                {"leanchecker":0,"leanchecker-paranoid":0},
                                "independent official/paranoid full checker discrepancy")
                out[variant].append(pair)
                report["profiles"][profile][variant]=dict(pairs=out[variant],complete=False)
                persist()
        # Package immutable representative evidence only after all warm pairs,
        # so compression cannot become an asymmetric inter-arm workload.
        for variant,mode,sample,arm in pending_witnesses:
            arm['representative_witness']=preserve_witness(args,profile,variant,mode,
                sample,json.loads(Path(sample['result_path']).read_bytes()))
        if receipt_comparison:
            report['profiles'][profile]['cross_mode_controls']=[
                cross_mode_control(q[target],source,target,first_early[source])
                for source,target in (modes,modes[::-1])]
            persist()
        # Each comparison policy independently authenticates and rechecks its own persisted acceptance.
        cold_modes=modes if receipt_comparison else ("retained_selected",)
        cold={}
        for mode in cold_modes:
            require(mode in first_early,"no actual accepted restart witness: "+mode)
            original=first_early[mode]
            root=Path(original["result_path"]).parent/"session"
            replay=q[mode].sample("early-definition","cold-restart",refs[mode],
                cold_root=root,replay_id=original["evidence_id"])
            fresh_result,audit=verified_result(replay,mode)
            old=json.loads(Path(original["result_path"]).read_bytes())
            require(fresh_result["export_sha256"]==old["export_sha256"] and
                    normalized(fresh_result)==normalized(old),"cold accepted decision changed: "+mode)
            cold[mode]=dict(passed=True,evidence_id=old["evidence_id"],
                source_sha256=old["export_sha256"],arm=actual_arm(replay,fresh_result,audit,root))
        report["profiles"][profile]["cold_restart"]=cold if receipt_comparison else cold['retained_selected']
        for mode in modes:
            q[mode].report["run_completed"]=True
            q[mode].flush()
            require(q[mode].report["correctness_passed"],"source authority, checker or full oracle admission failed")
        for variant in VARIANTS:
            pairs=out[variant]
            require(len(pairs)==args.repetitions and args.repetitions>=5,"incomplete paired comparison")
            def economics(field,seed):
                return scoped_economics([dict(apply_wall_seconds=x['arms'][candidate][field],
                    direct_wall_seconds=x['arms'][control][field]) for x in pairs],seed=seed,
                    scope=scope+' Observed '+field+'.',metric=field,candidate=candidate,control=control,
                    includes_setup=field=='setup_plus_apply_component_sum_seconds')
            cpu=scoped_economics([dict(
                apply_wall_seconds=x['arms'][candidate]['phases']['timings']['end_to_end_cpu_seconds'],
                direct_wall_seconds=x['arms'][control]['phases']['timings']['end_to_end_cpu_seconds'])
                for x in pairs],seed=20261028,scope=scope+' Complete apply CPU.',
                metric='cpu_seconds',candidate=candidate,control=control)
            direct={mode:scoped_economics([dict(apply_wall_seconds=x['arms'][mode]['wall_seconds'],
                direct_wall_seconds=x['arms'][mode]['direct_rust']['wall_seconds']) for x in pairs],seed=20261029,
                scope='Complete warm '+mode+' apply versus fresh full Rust check of the same live sealed snapshot; distinct from receipt comparison.',
                metric='wall_seconds',candidate=mode,control='same_snapshot_fresh_full_rust') for mode in modes}
            report["profiles"][profile][variant]=dict(pairs=pairs,complete=True,
                warm_economics=economics('wall_seconds',20261017),
                warm_cpu_economics=cpu,
                selected_kernel_economics=economics('kernel_seconds',20261027),
                persistence_economics=economics('persistence_seconds',20261030),
                setup_plus_one_apply_component_sum_economics=economics('setup_plus_apply_component_sum_seconds',20261031),
                direct_full_rust_economics=direct,
                median_startup_s={mode:statistics.median(x['arms'][mode]['setup_seconds'] for x in pairs) for mode in modes})
        persist()
    for path,h in report["source_sha256"].items():
        require(file_hash(Path(path))==h,"source drift during paired comparison")
    for name,h in report["binary_sha256"].items():
        require(file_hash(getattr(args,name))==h,"signed executable drift during paired comparison")
    report["qualified"]=report["completed"]=report['correctness_passed']=True
    persist()
    labels=(('Canonical JSON','Shared JSON') if receipt_comparison else ('Fresh selected','Retained selected'))
    lines=["# "+scope,"",
        "Same source-owned producer, HMAC authentication, conservative reuse, full sealed input and signed sparse receipts.",
        "Every arm has independent full Rust/index/partition/receipt audits; first pairs also have full C++ and paranoid checks.",
        "Warm apply excludes initial setup. Cold replay and setup plus one apply components are separate; no update-stream amortization.","",
        "| Source / edit | "+labels[0]+" warm (s) | "+labels[1]+" warm (s) | Saving | Wins | Bootstrap 95% ratio | Gate |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |"]
    for profile in ("original","expanded"):
        for variant in VARIANTS:
            e=report["profiles"][profile][variant]["warm_economics"];ci=e["bootstrap_ratio_interval_95"]
            lines.append(f"| {profile} / {variant} | {e['direct_median_wall_seconds']:.6f} | "
                f"{e['apply_median_wall_seconds']:.6f} | {(1-e['median_ratio'])*100:.2f}% | "
                f"{e['paired_wins']}/{e['paired_count']} | [{ci[0]:.5f},{ci[1]:.5f}] | {e['status']} |")
    lines += ["", "CPU, all phase/resource observations, same-input direct Rust comparisons, cold replay and representative full witnesses are preserved in the JSON reports.",
              "NO_SPEEDUP is a valid economic result and does not change the independent correctness qualification.",
              "Frozen bounded tests do not formally prove the retained parser bridge or qualify a multi-update lifetime."]
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
    if sys.argv[1:]==['--self-test']:
        if not self_test():raise SystemExit(1)
        return
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("protected","compare","receipt-compare"),required=True)
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
    return qualification(args) if args.mode=="protected" else compare(args,receipt_comparison=args.mode=="receipt-compare")

if __name__=="__main__":
    main()
