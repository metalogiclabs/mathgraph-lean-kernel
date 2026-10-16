#!/usr/bin/env python3
"""Exact-source causal comparison of full-index vs sparse-index transport.

The accepted receipt stays unchanged and carries the full index. Only the
index-session→consumer wire response changes. No speedup from future sparse
receipt storage is implied. Positive samples run mandatory fresh native index,
Rust and C++/paranoid oracles and actual signed acceptance validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys

from producer_delta import DeltaSession
from qualify_delta import Qualification, paired_economics, canonical, file_hash, write

MODES=('full_wire','sparse_wire')
VARIANTS=('early-definition','unrelated-definition')

class SparseSession(DeltaSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, sparse_index_wire=True, **kwargs)

def make_qualification(args, workloads, profile, mode):
    option=argparse.Namespace(
        workloads=workloads, producer=args.producer, checker=args.checker,
        indexer=args.indexer, index_session=args.index_session,
        full_checker=args.full_checker, authority_key=args.authority_key,
        out=args.out/profile/mode, repetitions=args.repetitions
    )
    q=Qualification(option)
    if mode=='sparse_wire':
        q.session_type=SparseSession
    return q

def clean_decisions(r):
    return [dict(index=row['index'], name=row['name'], status=row['status'],
                 reason=row['reason'], dependency_witness=row['dependency_witness'])
            for row in r['decisions']]

def inspected_result(sample, mode):
    if 'error' in sample or not sample.get('partition_audit') or not sample.get('persisted_acceptance_audit'):
        raise ValueError('missing independent sample qualification: '+str(sample.get('error')))
    result=json.loads(Path(sample['result_path']).read_bytes())
    if result['status']!='VERIFIED' or result.get('evidence_id') is None:
        raise ValueError('unwarranted or missing acceptance receipt')
    if result.get('checker_result',{}).get('code')!=0 or sample['direct_rust']['returncode']!=0:
        raise ValueError('actual checker or full Rust oracle declined')
    typed=result['typed_update']
    expected='baseline_patch_v1' if mode=='sparse_wire' else 'full_index_v1'
    if typed.get('index_wire')!=expected or typed.get('retained_graph_used') is not True:
        raise ValueError('wrong index transport or retained graph did not run')
    if mode=='sparse_wire':
        patch=typed.get('index_patch',{})
        if patch.get('schema')!='mathgraph.export-identity-baseline-patch.v1':
            raise ValueError('wrong sparse patch schema')
        if not isinstance(patch.get('declarations'), list):
            raise ValueError('missing changed declaration witnesses')
        if 'index' in typed:
            raise ValueError('sparse response leaked a complete index')
    if not sample.get('snapshot') or sample['snapshot']['sha256']!=result['export_sha256']:
        raise ValueError('sealed actual export identity mismatch')
    return result

def run(args):
    args.out.mkdir(parents=True,exist_ok=False)
    root_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    summary=dict(schema='mathgraph.sparse-index-wire-ab.v1',
                 exact_source_sha=root_sha,complete=False,correctness_passed=False,
                 comparison='same source/producer/indexer/checker; full vs typed sparse Rust index response',
                 measurement='warm source capture through authenticated persistence',
                 receipt_format='unchanged full-index signed acceptance, no sparse-receipt claim',
                 source_checksums={},executable_checksums={},profiles={})
    for p in ['src/identity.rs','src/bin/index_session.rs',
              'experiments/incremental/producer_delta.py',
              'experiments/incremental/benchmark_sparse_wire.py']:
        summary['source_checksums'][p]=file_hash(p)
    for p in ('producer','checker','indexer','index_session','full_checker'):
        summary['executable_checksums'][p]=file_hash(getattr(args,p))
    write(args.out/'summary.json',summary)
    for profile,workloads in [('original',args.original_workloads),
                              ('expanded',args.expanded_workloads)]:
        q={mode:make_qualification(args,workloads,profile,mode) for mode in MODES}
        ref={}
        for mode in MODES:
            q[mode].preflight()
            ref[mode]={v:q[mode].reference(v) for v in ('baseline',)+VARIANTS}
        if canonical(ref['full_wire'])!=canonical(ref['sparse_wire']):
            raise ValueError('full and sparse arms disagree about pinned genuine Lean indices')
        pairs={v:[] for v in VARIANTS}
        summary['profiles'][profile]={}
        for rep in range(args.repetitions):
            order=list(VARIANTS)
            random.Random(20261017+rep).shuffle(order)
            for v in order:
                ordered=MODES if (rep + (v=='unrelated-definition'))%2==0 else MODES[::-1]
                observations={}
                for mode in ordered:
                    sample=q[mode].sample(v,rep,ref[mode])
                    result=inspected_result(sample,mode)
                    observations[mode]=dict(
                        wall_seconds=sample['apply_wall_seconds'],
                        identity_seconds=result['timings']['identity_update_seconds'],
                        checked=result['counts']['rechecked'],
                        reused=result['counts']['reused'],
                        index_wire=result['typed_update']['index_wire'],
                        patch_declarations=len(result['typed_update'].get('index_patch',{}).get('declarations',[])),
                        export_sha256=result['export_sha256'],
                        checksum=hashlib.sha256(canonical(clean_decisions(result))).hexdigest(),
                        accepted=True, oracle_full_index=True,
                        cpp_oracles={name:log['returncode']
                          for name,log in sample.get('independent_kernels',{}).items()},
                        receipt_bytes=sample['persisted_acceptance_audit']['receipt_bytes'])
                for field in ('export_sha256','checksum','checked','reused','accepted'):
                    if observations['full_wire'][field]!=observations['sparse_wire'][field]:
                        raise ValueError('indexed identity or acceptance decision mismatch: '+field)
                if rep==0:
                    for mode in MODES:
                        if observations[mode]['cpp_oracles']!={'leanchecker':0,'leanchecker-paranoid':0}:
                            raise ValueError('C++ or paranoid independent oracle discrepancy')
                pairs[v].append(dict(variant=v,repetition=rep,order=list(ordered),arms=observations))
                summary['profiles'][profile][v]=dict(pairs=pairs[v],complete=False)
                write(args.out/'summary.json',summary)
        for v in VARIANTS:
            comparison=paired_economics([
                dict(apply_wall_seconds=x['arms']['sparse_wire']['wall_seconds'],
                     direct_wall_seconds=x['arms']['full_wire']['wall_seconds'])
                for x in pairs[v]],seed=20261017)
            identity_compare=paired_economics([
                dict(apply_wall_seconds=x['arms']['sparse_wire']['identity_seconds'],
                     direct_wall_seconds=x['arms']['full_wire']['identity_seconds'])
                for x in pairs[v]],seed=20261018)
            if len(pairs[v])!=args.repetitions or args.repetitions<5:
                raise ValueError('incomplete prespecified wire transport comparison')
            summary['profiles'][profile][v]=dict(
                pairs=pairs[v],complete=True,end_to_end=comparison,
                identity_phase=identity_compare,
                medians=dict(
                    full_wire=statistics.median(p['arms']['full_wire']['wall_seconds'] for p in pairs[v]),
                    sparse_wire=statistics.median(p['arms']['sparse_wire']['wall_seconds'] for p in pairs[v]),
                    sparse_patch_declarations=statistics.median(p['arms']['sparse_wire']['patch_declarations'] for p in pairs[v])
                ))
        # Replay the preexisting adverse scenarios against the opt-in sparse
        # transport, including changed bytes not reported by the source owner.
        q['sparse_wire'].controls()
        for mode in MODES:
            q[mode].report['run_completed']=True
            q[mode].flush()
            if q[mode].report['correctness_passed'] is not True:
                raise ValueError('required protected sparse/full correctness control failed')
        write(args.out/'summary.json',summary)
    for p,v in summary['source_checksums'].items():
        if file_hash(p)!=v: raise ValueError('source changed during qualification: '+p)
    for p,v in summary['executable_checksums'].items():
        if file_hash(getattr(args,p))!=v: raise ValueError('tool executable drift: '+p)
    summary['complete']=summary['correctness_passed']=True
    lines=['# Same-host sparse Rust identity response vs complete index response','',
           'Both arms sign the historical full acceptance receipt; this test only changes the index transport.',
           'Same real Lean source, Rust binary, source-owner producer and verifier policy. All fresh full-index and proof oracles pass.',
           '',
           '| Workload / edit | Full wire s | Sparse wire s | Change | Wins | 95% bootstrap ratio | Gate |',
           '| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for profile in ('original','expanded'):
        for v in VARIANTS:
            entry=summary['profiles'][profile][v]
            ec=entry['end_to_end']
            ci=ec['bootstrap_ratio_interval_95']
            lines.append(f"| {profile} / {v} | {entry['medians']['full_wire']:.6f} | "+
                        f"{entry['medians']['sparse_wire']:.6f} | "+
                        f"{(1-ec['median_ratio'])*100:.2f}% | {ec['paired_wins']}/{ec['paired_count']} | "+
                        f"[{ci[0]:.4f},{ci[1]:.4f}] | {ec['status']} |")
    lines += ['','The sparse branch is a typed transport optimization, NOT a new soundness theorem.',
              'Receipt serialization and full export parsing/materialization remain O(total).',
              'Any NO_SPEEDUP is retained as negative economic evidence.']
    (args.out/'summary.md').write_text('\n'.join(lines)+'\n')
    write(args.out/'summary.json',summary)
    print('\n'.join(lines))
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('original-workloads','expanded-workloads','producer','checker','indexer',
                 'index-session','full-checker','authority-key','out'):
        parser.add_argument('--'+flag,required=True,type=Path)
    parser.add_argument('--repetitions',type=int,default=5)
    args=parser.parse_args()
    if args.repetitions!=5: parser.error('frozen economic comparison requires exactly five pairs')
    args.producer=args.producer.resolve()
    args.checker=args.checker.resolve()
    args.indexer=args.indexer.resolve()
    args.index_session=args.index_session.resolve()
    args.full_checker=args.full_checker.resolve()
    args.authority_key=args.authority_key.resolve()
    args.original_workloads=args.original_workloads.resolve()
    args.expanded_workloads=args.expanded_workloads.resolve()
    args.out=args.out.resolve()
    return run(args)

if __name__=='__main__':
    sys.exit(main())
