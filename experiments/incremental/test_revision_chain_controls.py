#!/usr/bin/env python3
"""Fail-closed real-kernel controls for accepted predecessor continuation."""
import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import subprocess
import tempfile

import engine
from producer_delta import SOURCES, TRANSITION, seal, sha, sources_at
from revision_chain import RevisionChainSession
from qualify_delta import (audit_partition, command_run, configuration,
                           fresh_index, write)

REQUIRED_CONTROLS = (
    'first-parent-full-index-and-partition-parity',
    'returned-source-capture-does-not-alias-accepted-predecessor',
    'forged-hmac', 'changed-delta-without-authority',
    'source-capture-patch-substitution', 'source-capture-names-substitution',
    'authenticated-wrong-parent', 'authenticated-environment-drift', 'authenticated-version-drift',
    'source-outside-reported-region', 'false-change-name-hint', 'axiom-kind-assumption-change',
    'invalid-source-proof', 'toolchain-source-outside-policy',
    'unused-malformed-dag-zero-selected', 'signed-invalid-definition-proof',
    'foreign-issuer', 'receipt-policy-version-mismatch',
    'corrupt-chain-head', 'corrupt-source-capture', 'corrupt-current-receipt',
    'corrupt-transition', 'corrupt-delta', 'corrupt-representation', 'corrupt-genesis',
    'corrupt-baseline-receipt', 'corrupt-baseline-export',
    'deleted-latest-head-no-prefix-fallback', 'cold-start-requires-external-expected-head',
    'failed-persistence-does-not-promote-head',
    'cold-recovery-after-rejections-and-corruption-then-dependency-restoration',
    'real-dependency-edge-fallback-refresh-and-restore')


def run(args):
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('controls require fresh evidence output')
    out.mkdir(parents=True, exist_ok=True)
    args.workloads, args.binaries, args.producer = (p.resolve() for p in (args.workloads,args.binaries,args.producer))
    manifest = json.loads((args.workloads / 'manifest.json').read_bytes())
    report = dict(schema='mathgraph.revision-chain-controls.v1', passed=False,
                  source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  profile=manifest.get('profile','original-v1'), controls=[],
                  required_controls=list(REQUIRED_CONTROLS))
    def record(name, **detail):
        report['controls'].append(dict(name=name, passed=True, **detail))
        write(out / 'summary.json', report)
    source = out / 'live-source'
    initial = sources_at(args.workloads / 'baseline' / 'source')
    def put_sources(sources):
        for name, text in sources.items():
            path = source / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text)
    with tempfile.TemporaryDirectory(prefix='chain-controls-authority-') as private:
        key = Path(private) / 'issuer.key'
        key.write_bytes(os.urandom(32)); key.chmod(0o600)
        state = out / 'state'
        def session(**overrides):
            kwargs = dict(root=state,workloads=args.workloads,producer=args.producer,
                checker=args.binaries/'check-selected',indexer=args.binaries/'export-index',
                index_session=args.binaries/'index-session',authority_key=key,
                retained_checker=args.binaries/'check-selected-retained-session')
            kwargs.update(overrides)
            return RevisionChainSession(**kwargs)
        put_sources(initial)
        with session() as live:
            ready = live.start()
            baseline_index = copy.deepcopy(live.old['index'])
            p = ('IncrementalWorkload/Base.lean','def early : Nat := 17','def early : Nat := 23')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            first=live.apply(source,p,['IncrementalWorkload.early'])
            assert first['status']=='VERIFIED',first
            fresh,_=fresh_index(live.snapshot_path,args.binaries/'export-index',out/'fresh-first')
            partition=audit_partition(first,baseline_index,fresh)
            assert engine.encoded(fresh)==engine.encoded(live.old['index'])
            audit=live.audit_current_acceptance(fresh)
            record('first-parent-full-index-and-partition-parity',partition=partition,audit=audit)
            # Mutating a returned capture must not mutate private accepted state.
            live.last_transaction['source_capture']['sources'][p[0]]='forged after acceptance'
            assert live.baseline_sources[p[0]]==path.read_text()
            record('returned-source-capture-does-not-alias-accepted-predecessor')
            head,evidence=live.head_id,live.base_id
            accepted=dict(live.baseline_sources)
            accepted_result=copy.deepcopy(first)
        def records():return sorted(p.name for p in (state/'cache'/'records').glob('*.json'))
        def refusal(name, action, reason=None, overrides=None, kernel=False):
            put_sources(accepted)
            before=records()
            with session(**(overrides or {})) as live:
                observed=None;result=None
                try:
                    live.start(expected_head=head)
                    result=action(live)
                    if result is not None and result.get('status') in ('UNKNOWN','REJECTED'):
                        observed=result.get('reason',result.get('checker_result',{}).get('stderr',''))
                except (ValueError,KeyError,OSError,TypeError) as error:
                    observed=str(error)
                assert observed is not None, (name,'accepted or did not refuse',result)
                if reason is not None:assert reason in observed,(name,observed)
                assert live.poisoned and all(p is None or p.process.poll() is not None for p in
                    (live.producer,live.index,live.kernel_process)),name
                assert records()==before,(name,'persisted acceptance after refusal')
                details=dict(observed_refusal=observed,accepted_records_unchanged=True,poisoned=True)
                if result is not None:details['result']=result
                if kernel:
                    assert result['status']=='REJECTED' and result['checker_result']['code']==1,result
                    assert live.snapshot_path is not None
                    target=out/'negative-inputs'/(name+'.ndjson.gz');target.parent.mkdir(parents=True,exist_ok=True)
                    with Path(live.snapshot_path).open('rb') as r,gzip.open(target,'wb') as w:
                        import shutil
                        shutil.copyfileobj(r,w)
                    oracles={}
                    config=out/name/'config.json';write(config,configuration(live.snapshot_path))
                    for label,command in (
                        ('rust',[args.binaries/'sokonanoda',config]),
                        ('leanchecker',[manifest['tools']['leanchecker']['path'],'--from-export',live.snapshot_path]),
                        ('leanchecker-paranoid',[manifest['tools']['leanchecker-paranoid']['path'],'--from-export',live.snapshot_path])):
                        observed_process,_=command_run(command,out/name/label)
                        assert observed_process['returncode']==1 and not observed_process['timed_out'],observed_process
                        oracles[label]=observed_process
                    details['independent_kernel_rejections']=oracles
                    details['exact_negative_export_sha256']=sha(Path(live.snapshot_path).read_bytes())
                record(name,**details)
        def prepared(live):return live.prepare(source,None,[])
        def altered(live, edit):
            transaction=prepared(live);edit(transaction,live)
            return live.validate_apply(transaction)
        refusal('forged-hmac',lambda s:altered(s,lambda t,_:t['attestation'].__setitem__('hmac_sha256','0'*64)),
                'issuer authentication failed')
        refusal('changed-delta-without-authority',lambda s:altered(s,lambda t,_:t.__setitem__('delta_bytes',b'{}\n')),
                'changed-byte integrity failed')
        refusal('source-capture-patch-substitution',lambda s:altered(s,lambda t,_:t['source_capture'].__setitem__('patch',['bad','x','y'])),
                'prepared complete source capture was modified')
        refusal('source-capture-names-substitution',lambda s:altered(s,lambda t,_:t['source_capture'].__setitem__('claimed_names',['bad'])),
                'prepared complete source capture was modified')
        for name,field,value in (
                ('authenticated-wrong-parent','base_evidence_id','0'*64),
                ('authenticated-environment-drift','baseline_source_root','0'*64),
                ('authenticated-version-drift','provenance',{'schema':'foreign'})):
            def mutate(t,s,field=field,value=value):
                payload=copy.deepcopy(t['attestation']['payload']);payload[field]=value
                t['attestation']=seal(payload,s.key)
            refusal(name,lambda s,mutate=mutate:altered(s,mutate),'transition environment/version/base mismatch')
        def outside(s):
            path=source/'IncrementalWorkload/Leaves.lean'
            path.write_text(path.read_text().replace('n * n + 3','n * n + 99'))
            return s.apply(source,None,[])
        refusal('source-outside-reported-region',outside,'source modifications outside the reported patch')
        def wrong_names(s):
            p=('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            return s.apply(source,p,[])
        refusal('false-change-name-hint',wrong_names,'expected_changed_names differs from complete local comparison')
        def axiom_change(s):
            p=('IncrementalWorkload/Base.lean','def typed : Nat := 7','axiom typed : Nat')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            return s.apply(source,p,['IncrementalWorkload.typed'])
        refusal('axiom-kind-assumption-change',axiom_change,'metadata/kind drift')
        def invalid_source(s):
            p=('IncrementalWorkload/Leaves.lean','Eq.refl n','Nat.zero')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            return s.apply(source,p,['IncrementalWorkload.leaf'])
        refusal('invalid-source-proof',invalid_source)
        def environment(s):
            path=source/'lean-toolchain';path.write_text(path.read_text()+'\n')
            return s.apply(source,None,[])
        refusal('toolchain-source-outside-policy',environment,'source modifications outside the reported patch')
        # Issuer-authorized adversarial export bytes exercise the actual parser,
        # including bytes that do not affect any declaration fingerprint.
        rows=[json.loads(line) for line in Path(manifest['variants']['baseline']['path']).open()]
        exprmax=max(row['ie'] for row in rows if 'ie' in row)
        unused=engine.encoded(dict(ie=exprmax+100,bvar='not-an-integer'))+b'\n'
        def malformed(s):
            t=prepared(s);payload=copy.deepcopy(t['attestation']['payload'])
            t['delta_bytes']=unused;payload['delta_sha256']=sha(unused);t['attestation']=seal(payload,s.key)
            return s.validate_apply(t)
        refusal('unused-malformed-dag-zero-selected',malformed,kernel=True)
        names={0:''}
        for row in rows:
            if 'in' in row:
                part=row.get('str',row.get('num'));prefix=names[part['pre']]
                names[row['in']]=(prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
        early=copy.deepcopy(next(row for row in rows if 'def' in row and names[row['def']['name']]=='IncrementalWorkload.early'))
        early['def']['value']=next(row['ie'] for row in rows if row.get('sort')==0)
        def invalid_export(s):
            p=('IncrementalWorkload/Base.lean','def early : Nat := 23','def early : Nat := 29')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            t=s.prepare(source,p,['IncrementalWorkload.early']);delta=engine.encoded(early)+b'\n'
            payload=copy.deepcopy(t['attestation']['payload']);payload['delta_sha256']=sha(delta)
            t['delta_bytes']=delta;t['attestation']=seal(payload,s.key)
            return s.validate_apply(t)
        refusal('signed-invalid-definition-proof',invalid_export,kernel=True)
        wrong_key=Path(private)/'foreign.key';wrong_key.write_bytes(os.urandom(32))
        refusal('foreign-issuer',lambda _:None,'evidence issuer authentication failed',dict(authority_key=wrong_key))
        refusal('receipt-policy-version-mismatch',lambda _:None,'source-owner genesis provenance mismatch',
                dict(receipt_index_comparison='canonical_json'))
        state_info=json.loads((state/'session-state.json').read_bytes())
        receipt=json.loads((state/'cache'/'records'/(evidence+'.json')).read_bytes())['payload']
        representation=json.loads((state/'cache'/'representations'/(receipt['delta_representation']+'.json')).read_bytes())
        targets={
            'corrupt-chain-head':state/'cache'/'chain'/(head+'.json'),
            'corrupt-source-capture':state/'cache'/'source-captures'/(accepted_result['revision_chain']['source_capture_id']+'.json'),
            'corrupt-current-receipt':state/'cache'/'records'/(evidence+'.json'),
            'corrupt-transition':state/'cache'/'transitions'/(representation['transition_id']+'.json'),
            'corrupt-delta':state/'cache'/'deltas'/(representation['delta_sha256']+'.ndjson'),
            'corrupt-representation':state/'cache'/'representations'/(receipt['delta_representation']+'.json'),
            'corrupt-genesis':state/'cache'/'genesis'/(state_info['genesis_id']+'.json'),
            'corrupt-baseline-receipt':state/'baseline-cache'/'records'/(state_info['base_evidence_id']+'.json'),
            'corrupt-baseline-export':next((state/'baseline-cache'/'exports').glob('*.ndjson'))}
        for name,path in targets.items():
            raw=path.read_bytes();path.chmod(0o644);path.write_bytes(raw+b'corrupt')
            try:refusal(name,lambda _:None)
            finally:path.write_bytes(raw);path.chmod(0o444)
        path=targets['corrupt-chain-head'];saved=path.read_bytes();path.unlink()
        try:refusal('deleted-latest-head-no-prefix-fallback',lambda _:None)
        finally:engine.immutable_write(path,saved)
        with session() as cold:
            try:cold.start()
            except ValueError as error:assert 'requires caller expected head' in str(error)
            else:raise AssertionError('inferred latest head from ordinary cache')
            assert cold.poisoned
            record('cold-start-requires-external-expected-head')
        put_sources(accepted)
        with session() as failed:
            failed.start(expected_head=head)
            original_put=failed._put
            def fail_chain(category,raw,suffix):
                if category=='chain':raise OSError('injected chain persistence failure')
                return original_put(category,raw,suffix)
            failed._put=fail_chain
            p=('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            result=failed.apply(source,p,['IncrementalWorkload.unrelated'])
            assert result['status']=='UNKNOWN' and result['evidence_id'] is None and failed.poisoned,result
            assert failed.head_id==head and failed.base_id==evidence
            again=failed.apply(source,None,[])
            assert again['status']=='UNKNOWN' and failed.head_id==head
            record('failed-persistence-does-not-promote-head',result=result,
                   poisoned=True,
                   historical_orphan_receipt_allowed_only_after_genuine_kernel_acceptance=True,
                   expected_head_unchanged=True,subsequent_in_place_update_refused=True)
        put_sources(accepted)
        with session() as restored:
            restart=restored.start(expected_head=head)
            assert restored.base_id==evidence and restored.head_id==head and restart['replayed_revisions']==1
            p=('IncrementalWorkload/Base.lean','def early : Nat := 23','def early : Nat := 17')
            path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
            reverted=restored.apply(source,p,['IncrementalWorkload.early'])
            assert reverted['status']=='VERIFIED',reverted
            fresh,_=fresh_index(restored.snapshot_path,args.binaries/'export-index',out/'fresh-restored')
            assert engine.encoded(fresh)==engine.encoded(baseline_index)
            audit_partition(reverted,restored.last_parent_record['index'],fresh)
            assert restored.source_root==engine.digest(initial)
            record('cold-recovery-after-rejections-and-corruption-then-dependency-restoration',
                   replayed_revisions=restart['replayed_revisions'],restored_semantic_index=True,
                   retained_unused_dag_bytes_allow_different_export_sha=True)
            transitions=[]
            previous=fresh
            for p,name,expect_fallback in (
                (('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + IncrementalWorkload.early'),'unrelated',True),
                (('IncrementalWorkload/Base.lean','def early : Nat := 17','def early : Nat := 31'),'early',False),
                (('IncrementalWorkload/Leaves.lean','n * n + IncrementalWorkload.early','n * n + 3'),'unrelated',True),
                (('IncrementalWorkload/Base.lean','def early : Nat := 31','def early : Nat := 17'),'early',False)):
                path=source/p[0];path.write_text(path.read_text().replace(p[1],p[2]))
                result=restored.apply(source,p,['IncrementalWorkload.'+name])
                assert result['status']=='VERIFIED',result
                assert result['typed_update']['retained_graph_used'] is (not expect_fallback),result['typed_update']
                folder=out/'edge-transitions'/str(len(transitions))
                current,_=fresh_index(restored.snapshot_path,args.binaries/'export-index',folder/'fresh-index')
                assert engine.encoded(current)==engine.encoded(restored.old['index'])
                partition=audit_partition(result,previous,current)
                config=folder/'full.json';write(config,configuration(restored.snapshot_path))
                oracle,_=command_run([args.binaries/'sokonanoda',config],folder/'full-rust')
                assert oracle['returncode']==0 and not oracle['timed_out']
                transitions.append(dict(result=result,partition=partition,fresh_rust=oracle))
                previous=current
            assert engine.encoded(previous)==engine.encoded(baseline_index)
            record('real-dependency-edge-fallback-refresh-and-restore',transitions=transitions)
        assert len(report['controls'])==len(REQUIRED_CONTROLS)
        assert {c['name'] for c in report['controls']}==set(REQUIRED_CONTROLS)
        report['passed']=True
        write(out/'summary.json',report)
        print(json.dumps(dict(passed=True,controls=len(report['controls']),profile=report['profile'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workloads','producer','binaries','output'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
