#!/usr/bin/env python3
"""Independent causal full-vs-sparse signed acceptance receipts on real Lean/Std.

The source producer, Rust indexer (sparse wire), selected checker, HMAC issuer,
actual typed index and current policy are fixed. Only the issuer's *durable*
accepted receipt differs. Cold replays authenticate and reconstruct every
sparse receipt; fresh Rust/C++/paranoid kernels remain final oracles.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys

from producer_delta import DeltaSession, SPARSE_ACCEPTANCE
from qualify_delta import Qualification, paired_economics, canonical, file_hash, write

MODES=('full_receipt','sparse_receipt')
VARIANTS=('early-definition','unrelated-definition')

class FullReceiptSession(DeltaSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,sparse_index_wire=True,**kwargs)

class SparseReceiptSession(DeltaSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,sparse_index_wire=True,sparse_receipt=True,**kwargs)

def qualify(args,workloads,profile,mode):
    q=Qualification(argparse.Namespace(
        workloads=workloads,producer=args.producer,checker=args.checker,
        indexer=args.indexer,index_session=args.index_session,
        full_checker=args.full_checker,authority_key=args.authority_key,
        out=args.out/profile/mode,repetitions=args.repetitions))
    q.session_type=FullReceiptSession if mode=='full_receipt' else SparseReceiptSession
    return q

def normalized_decisions(result):
    return [dict(index=d['index'],name=d['name'],status=d['status'],reason=d['reason'],
                 dependency_witness=d['dependency_witness']) for d in result['decisions']]

def sample_audit(sample,mode):
    if sample.get('error') or not sample.get('partition_audit') or not sample.get('persisted_acceptance_audit'):
        raise ValueError('missing independent oracle or HMAC record audit: '+repr(sample.get('error')))
    result=json.loads(Path(sample['result_path']).read_bytes())
    if result.get('status')!='VERIFIED' or not result.get('evidence_id'):
        raise ValueError('receipt is not based on independently checked acceptance')
    if result['checker_result']['code']!=0 or sample['direct_rust']['returncode']!=0:
        raise ValueError('selected or fresh full Rust rejected accepted source')
    audit=sample['persisted_acceptance_audit']
    expected_schema=(SPARSE_ACCEPTANCE if mode=='sparse_receipt'
                     else 'mathgraph.incremental-lean.v1')
    if audit['receipt_schema']!=expected_schema or audit['contains_complete_index']!=(mode=='full_receipt'):
        raise ValueError('unqualified signed receipt format')
    if result['typed_update'].get('index_wire')!='baseline_patch_v1':
        raise ValueError('sparse index transfer did not run in both receipt arms')
    if result['export_sha256'] != sample['snapshot']['sha256']:
        raise ValueError('unsealed or modified current export')
    return result,audit

def run(args):
    args.out.mkdir(parents=True,exist_ok=False)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    report=dict(schema='mathgraph.sparse-accepted-receipt-ab.v1',
                source_sha=sha,complete=False,correctness_passed=False,
                comparison='same source-owning producer/indexer/kernel/sparse-wire; accepted receipt only',
                boundary='warm producer-to-authenticated-durable-receipt; cold setup separately measured',
                source_hashes={},binary_hashes={},profiles={},negative_lineage=[])
    for path in ('experiments/incremental/producer_delta.py',
                 'experiments/incremental/qualify_delta.py',
                 'experiments/incremental/benchmark_sparse_acceptance.py'):
        report['source_hashes'][path]=file_hash(path)
    for name in ('producer','checker','indexer','index_session','full_checker'):
        report['binary_hashes'][name]=file_hash(getattr(args,name))
    write(args.out/'summary.json',report)
    for profile,workloads in (('original',args.original_workloads),
                              ('expanded',args.expanded_workloads)):
        q={mode:qualify(args,workloads,profile,mode) for mode in MODES}
        ref={}
        for mode in MODES:
            q[mode].preflight()
            ref[mode]={v:q[mode].reference(v) for v in ('baseline',)+VARIANTS}
        if canonical(ref['full_receipt'])!=canonical(ref['sparse_receipt']):
            raise ValueError('input profiles have different fresh typed indexes')
        report['profiles'][profile]={}
        cases={variant:[] for variant in VARIANTS}
        first_sparse_early=None
        for rep in range(args.repetitions):
            order=list(VARIANTS)
            random.Random(20261017+rep).shuffle(order)
            for variant in order:
                modes=MODES if (rep+(variant=='unrelated-definition'))%2==0 else MODES[::-1]
                observations={}
                for mode in modes:
                    sample=q[mode].sample(variant,rep,ref[mode])
                    result,audit=sample_audit(sample,mode)
                    if variant=='early-definition' and rep==0 and mode=='sparse_receipt':
                        first_sparse_early=sample
                    observations[mode]=dict(
                        warm_wall_seconds=sample['apply_wall_seconds'],
                        receipt_bytes=audit['receipt_bytes'],
                        identity_wall_seconds=result['timings']['identity_update_seconds'],
                        persistence_wall_seconds=result['timings']['persistence_seconds'],
                        checked_count=result['counts']['rechecked'],
                        reused_count=result['counts']['reused'],
                        export_sha256=result['export_sha256'],
                        partition_sha256=hashlib.sha256(canonical(normalized_decisions(result))).hexdigest(),
                        oracle_cpp={name:v['returncode'] for name,v in sample.get('independent_kernels',{}).items()},
                        issuer_verified=audit['issuer_hmac_valid'] and audit['all_content_addresses_valid'])
                old,new=observations['full_receipt'],observations['sparse_receipt']
                for field in ('checked_count','reused_count','export_sha256','partition_sha256','issuer_verified'):
                    if old[field]!=new[field]:
                        raise ValueError('different verification result across receipt representations: '+field)
                if old['issuer_verified'] is not True:
                    raise ValueError('unverified issuer')
                if not new['receipt_bytes'] < old['receipt_bytes']:
                    raise ValueError('sparse signed receipt not actually smaller')
                if rep==0:
                    for mode in MODES:
                        if observations[mode]['oracle_cpp'] != {
                            'leanchecker':0,'leanchecker-paranoid':0}:
                            raise ValueError('independent C++ or paranoid oracle rejected')
                cases[variant].append(dict(repetition=rep,order=list(modes),arms=observations))
                report['profiles'][profile][variant]=dict(
                    complete=False,pairs=cases[variant])
                write(args.out/'summary.json',report)
        if first_sparse_early is None:
            raise ValueError('missing accepted sparse early receipt for cold replay')
        replay=q['sparse_receipt'].sample(
            'early-definition','cold-restart',ref['sparse_receipt'],
            cold_root=Path(first_sparse_early['result_path']).parent/'session',
            replay_id=first_sparse_early['evidence_id'])
        replay_result,replay_audit=sample_audit(replay,'sparse_receipt')
        first_result=json.loads(Path(first_sparse_early['result_path']).read_bytes())
        if replay_result['export_sha256']!=first_result['export_sha256']:
            raise ValueError('cold replay changed verified Lean export identity')
        if normalized_decisions(replay_result)!=normalized_decisions(first_result):
            raise ValueError('cold replay changed dependency-local obligations')
        report['profiles'][profile]['cold_sparse_replay']=dict(
            passed=True,verified_source_sha256=replay_result['export_sha256'],
            immutable_receipt_bytes=replay_audit['receipt_bytes'])
        # Challenge sparse-receipt mode with the inherited native negative
        # matrix: forged sources, foreign issuer, cache tampering, malformed
        # unused DAG rows, invalid type/proof, and scope drift.
        q['sparse_receipt'].controls()
        for mode in MODES:
            q[mode].report['run_completed']=True
            q[mode].flush()
            if q[mode].report['correctness_passed'] is not True:
                raise ValueError('original source/kernel or sparse receipt control failed')
        for variant in VARIANTS:
            pairs=cases[variant]
            e=paired_economics([
                dict(apply_wall_seconds=p['arms']['sparse_receipt']['warm_wall_seconds'],
                     direct_wall_seconds=p['arms']['full_receipt']['warm_wall_seconds'])
                for p in pairs],seed=20261017)
            receipt_reduction=1-statistics.median(p['arms']['sparse_receipt']['receipt_bytes'] for p in pairs)/statistics.median(
                p['arms']['full_receipt']['receipt_bytes'] for p in pairs)
            if len(pairs)!=5 or receipt_reduction<=0:
                raise ValueError('incomplete benchmark or non-sparse receipt')
            report['profiles'][profile][variant]=dict(
                complete=True,pairs=pairs,performance=e,receipt_size_reduction=receipt_reduction)
        write(args.out/'summary.json',report)
    for path,h in report['source_hashes'].items():
        if file_hash(path)!=h:
            raise ValueError('source modified during benchmark')
    for name,h in report['binary_hashes'].items():
        if file_hash(getattr(args,name))!=h:
            raise ValueError('verifier executable changed during benchmark')
    report['complete']=report['correctness_passed']=True
    write(args.out/'summary.json',report)
    lines=['# Same-host HMAC sparse acceptance receipt versus historical full receipt','',
           'Same real Lean/Std source, indexed typed-witness transfer, actual Rust selected kernel, HMAC issuer and policy.',
           'Fresh full Rust plus C++/paranoid kernel oracles and signed cold replay pass.',
           'Warm producer-to-persistence wall includes receipt issuance; initial setup excluded.','',
           '| Workload / edit | Full receipt s | Sparse receipt s | Saving | Paired wins | Receipt bytes saved | Gate |',
           '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for profile in ('original','expanded'):
        for variant in VARIANTS:
            entry=report['profiles'][profile][variant]
            e=entry['performance']
            lines.append(
                f"| {profile} / {variant} | {e['direct_median_wall_seconds']:.6f} | "
                f"{e['apply_median_wall_seconds']:.6f} | "
                f"{(1-e['median_ratio'])*100:.2f}% | {e['paired_wins']}/{e['paired_count']} | "
                f"{entry['receipt_size_reduction']*100:.2f}% | {e['status']} |")
    lines += ['','This is a bounded authenticated receipt representation, not a new kernel or general soundness proof.',
              'NO_SPEEDUP is preserved if entire warm transaction does not improve.',
              'Whole-composite materialization/parser, baseline authentication and memory index remain O(total).']
    (args.out/'summary.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('original-workloads','expanded-workloads','producer','checker','indexer',
              'index-session','full-checker','authority-key','out'):
        p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--repetitions',type=int,default=5)
    args=p.parse_args()
    if args.repetitions!=5:
        p.error('exactly five paired samples required')
    for name in ('original_workloads','expanded_workloads','producer','checker','indexer',
                 'index_session','full_checker','authority_key','out'):
        setattr(args,name,getattr(args,name).resolve())
    return run(args)

if __name__=='__main__':
    sys.exit(main())
