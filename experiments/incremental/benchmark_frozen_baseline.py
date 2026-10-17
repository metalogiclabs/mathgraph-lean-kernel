#!/usr/bin/env python3
"""Frozen session-owned verified baseline vs per-warm mutable-disk rehash.

The active HMAC issuer, full selected Rust parser/kernel, typed sparse wire,
typed sparse signed acceptance receipt and original reuse predicate are held
fixed. Only source of already-admitted baseline bytes changes. Cold restart
must reauthenticate immutable durable evidence; disk corruption while warm
cannot influence the historical verified source snapshot actually checked.
"""
import argparse
import hashlib
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

from build_workloads import EDITS
from producer_delta import DeltaSession
from qualify_delta import (Qualification, NAMES, paired_economics,
                           canonical, file_hash, write, fresh_index,
                           audit_partition, audit_receipt, sealed_snapshot)
from producer_delta import SPARSE_ACCEPTANCE

MODES=('durable_rehash','session_snapshot')
VARIANTS=('early-definition','unrelated-definition')

class DurableRehash(DeltaSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,sparse_index_wire=True,sparse_receipt=True,
                         frozen_baseline=False,**kwargs)

class SessionSnapshot(DeltaSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,sparse_index_wire=True,sparse_receipt=True,
                         frozen_baseline=True,**kwargs)

def qual(args,profile,mode,workloads):
    q=Qualification(argparse.Namespace(
        workloads=workloads,producer=args.producer,checker=args.checker,
        indexer=args.indexer,index_session=args.index_session,
        full_checker=args.full_checker,authority_key=args.authority_key,
        out=args.out/profile/mode,repetitions=args.repetitions))
    q.session_type=DurableRehash if mode=='durable_rehash' else SessionSnapshot
    return q

def normalized(result):
    return [dict(index=d['index'],name=d['name'],status=d['status'],reason=d['reason'],
                 dependency_witness=d['dependency_witness']) for d in result['decisions']]

def check_sample(sample,mode):
    if sample.get('error') or 'partition_audit' not in sample or 'persisted_acceptance_audit' not in sample:
        raise ValueError('independent warm sample declined: '+str(sample.get('error')))
    result=json.loads(Path(sample['result_path']).read_bytes())
    if (result.get('status')!='VERIFIED' or not result.get('evidence_id') or
        result.get('checker_result',{}).get('code')!=0 or
        sample['direct_rust']['returncode']!=0):
        raise ValueError('missing genuine accepted source or fresh Rust oracle')
    expected='source-owned-frozen-bytes-v1' if mode=='session_snapshot' else 'rehashed-durable-bytes-v1'
    if result['timings']['baseline_authority']!=expected:
        raise ValueError('incorrect actual authenticated baseline byte source')
    if mode=='session_snapshot':
        if result['producer_provenance'].get('baseline_authority')!=expected:
            raise ValueError('frozen source authority not in producer HMAC policy')
    elif 'baseline_authority' in result['producer_provenance']:
        raise ValueError('unannounced provenance change to historical disk arm')
    audit=sample['persisted_acceptance_audit']
    if (audit['receipt_schema']!=SPARSE_ACCEPTANCE or audit['contains_complete_index'] or
        audit['issuer_hmac_valid'] is not True or
        audit['all_content_addresses_valid'] is not True):
        raise ValueError('sparse receipt failed independent HMAC and typed-index audit')
    if sample['snapshot']['sha256']!=result['export_sha256']:
        raise ValueError('actual sealed export not bound to acceptance evidence')
    return result,audit

def warm_disk_mutation_control(q,refs,root):
    """Prove mutable backing corruption cannot change already frozen bytes.

    Cold restart must refuse the corrupt durable store. Restoring exact bytes
    permits independent cold re-check and reconstruction of the same acceptance.
    """
    session=q.new_session(root)
    session.start()
    filename=session.baseline_cache/'exports'/(session.old['export_sha256']+'.ndjson')
    before=filename.read_bytes()
    if hashlib.sha256(before).hexdigest()!=session.old['export_sha256']:
        raise ValueError('control baseline is already corrupted')
    filename.chmod(0o600)
    filename.write_bytes(before+b'\nMUTATED_DURABLE_STORAGE_AFTER_ADMISSION\n')
    if file_hash(filename)==session.old['export_sha256']:
        raise ValueError('control failed to corrupt durable store')
    try:
        result=session.apply(
            source_dir=q.workloads/'early-definition'/'source',
            patch=EDITS['early-definition'],
            claimed_names=NAMES['early-definition'])
        if result.get('status')!='VERIFIED':
            raise ValueError('immutable historical snapshot was unexpectedly rewritten: '+str(result))
        snapshot=Path(session.snapshot_path)
        sealed=sealed_snapshot(snapshot)
        if sealed['sha256']!=result['export_sha256']:
            raise ValueError('warm session accepted changed source bytes unexpectedly')
        fresh,process=fresh_index(snapshot,q.args.indexer,
                                 q.out/'controls'/'post-corruption-full-index')
        if process['returncode']!=0 or canonical(fresh)!=canonical(refs['early-definition']):
            raise ValueError('fresh independent full index disagrees after disk corruption')
        partition=audit_partition(result,refs['baseline'],fresh)
        if partition['actual_kernel_checked']!=result['counts']['rechecked']:
            raise ValueError('selected real kernel partition disagrees')
        full=q.full_oracle(snapshot,q.out/'controls'/'post-corruption-full-rust')
        if full['timed_out'] or full['returncode']!=0:
            raise ValueError('fresh full Rust did not accept exact immutable snapshot')
        accepted_id=result['evidence_id']
        original_outcome=dict(export_sha256=result['export_sha256'],
                              decisions=normalized(result),receipt_id=accepted_id)
    finally:
        session.close()
    # A completely new process/session must validate durable bytes again and
    # deny the historical baseline when persistent storage is corrupt.
    cold=q.new_session(root)
    try:
        try:
            cold.start()
        except ValueError as ex:
            if 'baseline storage corruption' not in str(ex):
                raise ValueError('wrong cold refusal: '+str(ex))
        else:
            raise ValueError('corrupted durable cache accepted during cold restart')
    finally:
        cold.close()
    filename.write_bytes(before)
    filename.chmod(0o444)
    cold=q.new_session(root)
    try:
        cold.start()
        restored=cold.replay(accepted_id)
        if (restored.get('status')!='VERIFIED' or
            restored['export_sha256']!=original_outcome['export_sha256'] or
            normalized(restored)!=original_outcome['decisions']):
            raise ValueError('exact historical proof was not restored by cold replay')
        audit=audit_receipt(root,restored,refs['early-definition'],q.args.authority_key.read_bytes())
        if (not audit['issuer_hmac_valid'] or audit['receipt_schema']!=SPARSE_ACCEPTANCE):
            raise ValueError('restored acceptance was not issuer authenticated')
    finally:
        cold.close()
    return dict(passed=True,corrupted_disk_refused_on_cold_restart=True,
                warm_used_exact_immutable_source=True,
                restored_cold_independent_replay=True,
                historical_evidence_id=accepted_id,
                sealed_export_sha256=original_outcome['export_sha256'])

def run(args):
    args.out.mkdir(parents=True,exist_ok=False)
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    summary=dict(schema='mathgraph.frozen-baseline-session-ab.v1',
                 source_sha=source_sha,complete=False,correctness_passed=False,
                 boundary='same source owner, sparse receipt and kernel; only warm baseline input source differs',
                 setup_excluded=True,source_hashes={},binary_hashes={},profiles={})
    for f in ('experiments/incremental/producer_delta.py',
              'experiments/incremental/benchmark_frozen_baseline.py'):
        summary['source_hashes'][f]=file_hash(f)
    for name in ('producer','checker','indexer','index_session','full_checker'):
        summary['binary_hashes'][name]=file_hash(getattr(args,name))
    write(args.out/'summary.json',summary)
    for profile,workloads in [('original',args.original_workloads),
                              ('expanded',args.expanded_workloads)]:
        q={mode:qual(args,profile,mode,workloads) for mode in MODES}
        references={}
        for mode in MODES:
            q[mode].preflight()
            references[mode]={v:q[mode].reference(v) for v in ('baseline',)+VARIANTS}
        if canonical(references[MODES[0]])!=canonical(references[MODES[1]]):
            raise ValueError('pinned full native input identities differ')
        cases={v:[] for v in VARIANTS}
        first_snapshot=None
        summary['profiles'][profile]={}
        for rep in range(args.repetitions):
            order=list(VARIANTS)
            random.Random(20261017+rep).shuffle(order)
            for variant in order:
                modes=MODES if (rep + (variant=='unrelated-definition'))%2==0 else MODES[::-1]
                arms={}
                for mode in modes:
                    sample=q[mode].sample(variant,rep,references[mode])
                    outcome,audit=check_sample(sample,mode)
                    if rep==0 and variant=='early-definition' and mode=='session_snapshot':
                        first_snapshot=sample
                    arms[mode]=dict(
                        end_to_end_seconds=sample['apply_wall_seconds'],
                        baseline_validation_seconds=outcome['timings']['baseline_validation_seconds'],
                        producer_seconds=outcome['timings']['producer_seconds'],
                        persistence_seconds=outcome['timings']['persistence_seconds'],
                        selected_checking_seconds=outcome['timings']['checking_seconds'],
                        checked_count=outcome['counts']['rechecked'],
                        reused_count=outcome['counts']['reused'],
                        export_sha256=outcome['export_sha256'],
                        decisions_hash=hashlib.sha256(canonical(normalized(outcome))).hexdigest(),
                        receipt_bytes=audit['receipt_bytes'],
                        oracle_cpp={name:v['returncode'] for name,v in sample.get('independent_kernels',{}).items()},
                        accepted=True)
                for field in ('checked_count','reused_count','export_sha256',
                              'decisions_hash','accepted'):
                    if arms[MODES[0]][field]!=arms[MODES[1]][field]:
                        raise ValueError('baseline-source choice changes verified result: '+field)
                if rep==0:
                    for mode in MODES:
                        if arms[mode]['oracle_cpp']!={'leanchecker':0,'leanchecker-paranoid':0}:
                            raise ValueError('official C++ and paranoid kernel disagreement')
                cases[variant].append(dict(repetition=rep,order=list(modes),arms=arms))
                summary['profiles'][profile][variant]=dict(complete=False,pairs=cases[variant])
                write(args.out/'summary.json',summary)
        if first_snapshot is None:
            raise ValueError('missing frozen snapshot cold replay fixture')
        cold=q['session_snapshot'].sample(
            'early-definition','cold-restart',references['session_snapshot'],
            cold_root=Path(first_snapshot['result_path']).parent/'session',
            replay_id=first_snapshot['evidence_id'])
        cold_result,_audit=check_sample(cold,'session_snapshot')
        original=json.loads(Path(first_snapshot['result_path']).read_bytes())
        if (cold_result['export_sha256']!=original['export_sha256'] or
            normalized(cold_result)!=normalized(original)):
            raise ValueError('cold replay diverged from exact earlier proof')
        summary['profiles'][profile]['cold_replay']=True
        q['session_snapshot'].controls()
        hard=warm_disk_mutation_control(
            q['session_snapshot'],references['session_snapshot'],
            q['session_snapshot'].out/'controls'/'frozen-warm-durable-corruption'/'session')
        summary['profiles'][profile]['durable_corruption_control']=hard
        for mode in MODES:
            q[mode].report['run_completed']=True
            q[mode].flush()
            if q[mode].report['correctness_passed'] is not True:
                raise ValueError('required full fresh kernel/protected control failed')
        for variant in VARIANTS:
            rows=cases[variant]
            economic=paired_economics([
                dict(apply_wall_seconds=p['arms']['session_snapshot']['end_to_end_seconds'],
                     direct_wall_seconds=p['arms']['durable_rehash']['end_to_end_seconds'])
                for p in rows],seed=20261017)
            baseline=paired_economics([
                dict(apply_wall_seconds=p['arms']['session_snapshot']['baseline_validation_seconds'],
                     direct_wall_seconds=p['arms']['durable_rehash']['baseline_validation_seconds'])
                for p in rows],seed=20261018)
            if len(rows)!=5: raise ValueError('incomplete five paired source snapshots')
            summary['profiles'][profile][variant]=dict(
                complete=True,pairs=rows,performance=economic,baseline_validation=baseline,
                setup_median_seconds={
                    mode:statistics.median(q[mode].report['samples'][i]['setup_wall_seconds']
                      for i in range(len(q[mode].report['samples']))
                      if q[mode].report['samples'][i]['variant']==variant and
                        type(q[mode].report['samples'][i]['repetition']) is int)
                    for mode in MODES})
        write(args.out/'summary.json',summary)
    for path,expected in summary['source_hashes'].items():
        if file_hash(path)!=expected:raise ValueError('source changed while measuring')
    for name,expected in summary['binary_hashes'].items():
        if file_hash(getattr(args,name))!=expected:raise ValueError('verifier executable drift')
    summary['complete']=summary['correctness_passed']=True
    write(args.out/'summary.json',summary)
    lines=['# Retained immutable baseline vs repeated durable HMAC rehash A/B','',
           'Same actual source-owning producer, same sparse signed receipt, same Rust selected kernel and C++/paranoid oracles.',
           'Five paired host repetitions; warm producer-to-persistence cost, setup excluded.','',
           '| Workload / edit | Durable full rehash s | Immutable session snapshot s | Saving | Pairs won | Gate |',
           '| --- | ---: | ---: | ---: | ---: | --- |']
    for profile in ('original','expanded'):
        for variant in VARIANTS:
            v=summary['profiles'][profile][variant]['performance']
            lines.append(f"| {profile} / {variant} | {v['direct_median_wall_seconds']:.6f} | "
                         f"{v['apply_median_wall_seconds']:.6f} | "
                         f"{(1-v['median_ratio'])*100:.2f}% | "
                         f"{v['paired_wins']}/{v['paired_count']} | {v['status']} |")
    lines+=['','Corrupting durable baseline *after* live admission cannot alter the immutable checked snapshot;',
            'cold restart independently refuses the corruption; exact bytes restoration permits genuine cold replay.',
            'A positive warm time does NOT prove universal change-proportional total cost, cold superiority or persistent-storage availability.',
            'Full-export parser/materialization and full typed in-memory index remain O(total).']
    (args.out/'summary.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original-workloads','expanded-workloads','producer','checker','indexer',
                 'index-session','full-checker','authority-key','out'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--repetitions',type=int,default=5)
    args=p.parse_args()
    if args.repetitions!=5:p.error('prespecified test requires five full pairs')
    for name in ('original_workloads','expanded_workloads','producer','checker','indexer',
                 'index_session','full_checker','authority_key','out'):
        setattr(args,name,getattr(args,name).resolve())
    return run(args)

if __name__=='__main__':
    sys.exit(main())
