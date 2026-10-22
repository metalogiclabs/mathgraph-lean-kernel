"""Independent review of the frozen 32-control matrix. Standard library only.

Historical private-key HMAC validity is not reauthenticated here. The compact
artifact preserves full-native index outputs and genuine process outcome/output
witnesses for topology controls, plus exact complete rejected inputs. It omits
the restored step-2 acceptance record; the first topology parent's identifier is
checked against its decision origins and later topology links are exact.
"""
import ast
import gzip
import hashlib
import re
import subprocess

from artifacts import canonical, hexid, loads, require
from reuse_rule import validate_index, validate_partition

CONTROL_SOURCE = 'experiments/incremental/test_revision_chain_controls.py'
# The exact four frozen control/chain summary wrappers retain complete
# per-declaration decisions. Keep their metadata cap separate from generic logs.
CONTROL_REPORT_BYTES = 512 * 1024 * 1024
NEGATIVES = ('signed-invalid-definition-proof', 'unused-malformed-dag-zero-selected')
PARTITION_FIELDS = frozenset(('actual_kernel_checked','actual_kernel_total','independently_replayed_reused',
                              'checked_indices','reused_indices','identity_witnesses_checked'))


def required_names(repo, source):
    require(re.fullmatch('[0-9a-f]{40}',source) is not None, 'exact source SHA required for controls')
    raw=subprocess.check_output(['git','-C',str(repo),'show',source+':'+CONTROL_SOURCE])
    tree=ast.parse(raw)
    values=[node.value for node in tree.body if isinstance(node,ast.Assign) and
            any(isinstance(target,ast.Name) and target.id=='REQUIRED_CONTROLS' for target in node.targets)]
    require(len(values)==1, 'frozen source has ambiguous required control matrix')
    names=ast.literal_eval(values[0])
    require(type(names) is tuple and len(names)==32 and len(set(names))==32 and
            all(type(name) is str and name for name in names), 'frozen required matrix is not exactly32')
    return names


def validate_header(report, expected, source, profile):
    require(type(report) is dict and report.get('schema')=='mathgraph.revision-chain-controls.v1' and
            report.get('source_sha')==source and report.get('passed') is True,
            'controls report incomplete, wrong-source or wrong-domain')
    require(report.get('profile')==('original-v1' if profile=='original' else 'std-hashmap-expanded-v1'),
            'controls workload profile differs')
    required,rows=report.get('required_controls'),report.get('controls')
    require(type(required) is list and len(required)==32 and len(set(required))==32 and set(required)==set(expected),
            'report self-declared required matrix differs from exact frozen32')
    require(type(rows) is list and len(rows)==32 and
            all(type(row) is dict and row.get('passed') is True and type(row.get('name')) is str for row in rows),
            'controls matrix missing/failed actual observations')
    require(len({row['name'] for row in rows})==32 and {row['name'] for row in rows}==set(expected),
            'actual controls omitted, duplicated or substituted')
    return {row['name']:row for row in rows}


def validate_result_profile(result,profile,count):
    require(type(count) is int and count>0 and result.get('producer_provenance',{}).get('profile')==
            ('original-v1' if profile=='original' else 'std-hashmap-expanded-v1') and
            type(result.get('counts',{}).get('total')) is int and result['counts']['total']==count,
            'control result workload profile/count differs from complete baseline reference')


def validate_zero_selected_rejection(result,parent_index,parent_evidence):
    require(hexid(parent_evidence) and result.get('previous_evidence')==parent_evidence,
            'zero-selected rejection targets a foreign admitted parent')
    counts=result.get('counts',{})
    require(all(type(counts.get(k)) is int and counts[k]==v for k,v in
            dict(total=parent_index['count'],scheduled=0,reused=parent_index['count'],invalidated=0).items()) and
            counts.get('rechecked') is None, 'zero-selected rejection hid scheduled or completed obligations')
    decisions=result.get('decisions')
    require(type(decisions) is list and len(decisions)==parent_index['count'],
            'zero-selected rejection omitted complete reused decisions')
    for decision,row in zip(decisions,parent_index['declarations']):
        require(type(decision.get('index')) is int and decision['index']==row['index'] and
                decision.get('name')==row['name'] and decision.get('status')=='VERIFIED_REUSED' and
                decision.get('evidence_id')==parent_evidence and
                canonical(decision.get('dependency_witness'))==canonical(dict(own=row['own'],closure=row['closure'],direct=row['deps'])),
                'zero-selected rejection changed a parent decision witness or evidence origin')


def _configuration(value):
    require(type(value) is dict and set(value)=={'export_file_path','use_stdin','permitted_axioms',
            'unpermitted_axiom_hard_error','num_threads','nat_extension','string_extension','print_success_message'} and
            type(value['export_file_path']) is str and value['use_stdin'] is False and
            value['permitted_axioms']==['propext','Classical.choice','Quot.sound'] and
            value['unpermitted_axiom_hard_error'] is True and type(value['num_threads']) is int and
            value['num_threads']==1 and value['nat_extension'] is True and value['string_extension'] is True and
            value['print_success_message'] is True, 'control full-kernel/index configuration differs from policy')
    return value


def _outputs(store, process, code):
    require(type(process) is dict and type(process.get('returncode')) is int and
            process['returncode']==code and process.get('timed_out') is False,
            'control real process failed, timed out or has wrong rejection code')
    require(type(process.get('command')) is list and process['command'] and
            all(type(part) is str for part in process['command']), 'control process command missing')
    for kind in ('stdout','stderr'):
        raw=store.saved(process[kind+'_path'])
        require(hexid(process.get(kind+'_sha256')) and hashlib.sha256(raw).hexdigest()==process[kind+'_sha256'],
                'actual control process output changed: '+kind)


def _native_index(store, folder, expected_binary):
    value=loads(store.saved_member(store.join(folder,'index.json')))
    process=loads(store.saved_member(store.join(folder,'process.json')))
    _outputs(store,process,0)
    require(len(process['command'])==2 and process['command'][0]==expected_binary,
            'topology full-native process uses a different executable')
    stdout=loads(store.saved(process['stdout_path']))
    require(canonical(stdout)==canonical(value), 'topology full index differs from actual native stdout')
    validate_index(value)
    config=_configuration(loads(store.saved(process['command'][1])))
    return value,config


def _manifest(store):
    member=store.join(store.artifact,'revision-control-archive.json')
    require(member in store.members, 'missing control summary compressed-byte manifest')
    records=store.json(member)
    expected={store.join(store.artifact,folder,'summary.json.gz') for folder in
              ('revision-chain-tests-original','revision-chain-tests-expanded',
               'revision-chain-controls-original','revision-chain-controls-expanded')}
    require(type(records) is list and len(records)==4, 'compressed control/archive manifest must cover all four reports')
    indexed={}
    for record in records:
        require(type(record) is dict and set(record)=={'path','sha256','bytes','uncompressed_path',
                'uncompressed_sha256','uncompressed_bytes'} and
                hexid(record['sha256']) and hexid(record['uncompressed_sha256']) and
                type(record['bytes']) is int and record['bytes']>0 and
                type(record['uncompressed_bytes']) is int and record['uncompressed_bytes']>0,
                'invalid compressed control report descriptor')
        path=store.map(record['path'])
        require(path not in indexed and path in expected and
                store.map(record['uncompressed_path'])==path[:-3], 'substituted or duplicate compressed control report')
        # `path in expected` above scopes this allowance to the exact four
        # frozen summary wrappers, including the expanded4-step cold probe.
        require(record['uncompressed_bytes']<=CONTROL_REPORT_BYTES, 'compressed control/archive report exceeds scoped decoded limit')
        require(store.stream_hash(path)==(record['sha256'],record['bytes']) and
                store.stream_hash(path,True)==(record['uncompressed_sha256'],record['uncompressed_bytes']),
                'compressed/uncompressed control report SHA/size mismatch')
        indexed[path]=record
    require(set(indexed)==expected, 'compressed control report coverage incomplete')
    return indexed


def _report(store,member):
    with store.open(member) as raw,gzip.GzipFile(fileobj=raw) as stream:
        data=stream.read(CONTROL_REPORT_BYTES+1)
    require(len(data)<=CONTROL_REPORT_BYTES, 'expanded controls report exceeds bounded JSON reader')
    return loads(data)


def validate_controls(store,repo,source,smoke=False):
    names=required_names(repo,source)
    summary_members=[store.join(store.artifact,'revision-chain-controls-'+profile,'summary.json.gz')
                     for profile in ('original','expanded')]
    any_controls=any(member in store.members for member in summary_members)
    if smoke and not any_controls:
        return dict(status='OMITTED_CONTROLS_SMOKE_UNQUALIFIED',qualified=False,profiles={},negative_inputs=[],
                    required_controls=list(names),historical_hmac_reauthenticated=False,
                    scope='Local lifecycle smoke omits the independent32-control CI artifacts; no control qualification claimed.')
    require(all(member in store.members for member in summary_members), 'both exact32-control reports required')
    descriptors=_manifest(store)
    lifecycle=store.json(store.summary_member)
    binaries=lifecycle['binary_sha256']
    results,negative_inputs={},[]
    for profile,summary_member in zip(('original','expanded'),summary_members):
        report=_report(store,summary_member)
        rows=validate_header(report,names,source,profile)
        root=store.join(store.artifact,'revision-chain-controls-'+profile)
        baseline_process=lifecycle['profiles'][profile]['references']['0']['native_process']
        _outputs(store,baseline_process,0)
        baseline_index=loads(store.saved(baseline_process['stdout_path']))
        validate_index(baseline_index)
        # Every generic refusal has actual poison/no-new-receipt observations.
        special={'first-parent-full-index-and-partition-parity',
                 'returned-source-capture-does-not-alias-accepted-predecessor',
                 'cold-start-requires-external-expected-head','failed-persistence-does-not-promote-head',
                 'cold-recovery-after-rejections-and-corruption-then-dependency-restoration',
                 'real-dependency-edge-fallback-refresh-and-restore'}
        for name,row in rows.items():
            if name not in special:
                require(row.get('accepted_records_unchanged') is True and row.get('poisoned') is True and
                        type(row.get('observed_refusal')) is str and row['observed_refusal'],
                        'refusal did not preserve accepted records and poison processes: '+name)
        first=rows['first-parent-full-index-and-partition-parity']
        require(type(first.get('partition')) is dict and set(first['partition'])==PARTITION_FIELDS and
                first.get('audit',{}).get('issuer_hmac_valid') is True and
                first['audit'].get('all_content_addresses_valid') is True,
                'first-parent full-index/receipt parity witness missing')
        accepted_parent=first['audit'].get('evidence_id')
        require(hexid(accepted_parent), 'negative-control accepted predecessor identity missing')
        early_process=lifecycle['profiles'][profile]['references']['1']['native_process']
        _outputs(store,early_process,0)
        early_index=loads(store.saved(early_process['stdout_path']))
        validate_index(early_index)
        for name in NEGATIVES:
            row=rows[name];result=row['result'];oracles=row['independent_kernel_rejections']
            validate_result_profile(result,profile,baseline_index['count'])
            require(result.get('previous_evidence')==accepted_parent, 'negative control substituted admitted predecessor')
            require(result.get('status')=='REJECTED' and result.get('evidence_id') is None and
                    result.get('action_authorization')=='NONE' and type(result.get('checker_result')) is dict and
                    type(result['checker_result'].get('code')) is int and result['checker_result']['code']==1,
                    'invalid bytes received acceptance or a non-kernel failure: '+name)
            require(type(result.get('counts')) is dict and type(result['counts'].get('total')) is int and
                    result['counts']['total']>0 and type(result['counts'].get('scheduled')) is int and
                    result['counts']['scheduled']>=0, 'negative selected/total count witness missing')
            if name=='unused-malformed-dag-zero-selected':
                validate_zero_selected_rejection(result,early_index,accepted_parent)
            native=result.get('native_kernel_report')
            require(type(native) is dict and native.get('status')=='rejected' and
                    type(native.get('code')) is int and native['code']==1,
                    'retained parser did not itself reject negative bytes')
            require(type(oracles) is dict and set(oracles)=={'rust','leanchecker','leanchecker-paranoid'},
                    'negative missing Rust/C++/paranoid actual process witnesses')
            config=None
            for tool,process in oracles.items():
                _outputs(store,process,1)
                expected_binary=binaries['full_checker' if tool=='rust' else profile+':'+tool]['path']
                require(process['command'][0]==expected_binary, 'negative oracle binary differs from measured executable')
                if tool=='rust':
                    require(len(process['command'])==2, 'negative Rust command differs')
                    config=_configuration(loads(store.saved(process['command'][1])))
            require(config is not None, 'negative exact-input configuration missing')
            for tool in ('leanchecker','leanchecker-paranoid'):
                require(oracles[tool]['command']==[binaries[profile+':'+tool]['path'],'--from-export',config['export_file_path']],
                        'negative full-kernel controls checked different inputs')
            member=store.join(root,'negative-inputs',name+'.ndjson.gz')
            identity,size=store.stream_hash(member,True)
            require(hexid(row.get('exact_negative_export_sha256')) and
                    identity==row['exact_negative_export_sha256']==result['export_sha256'] and
                    size==result['representation']['export_bytes'], 'exact complete rejected input differs')
            compressed,compressed_size=store.stream_hash(member)
            negative_inputs.append(dict(sha256=identity,bytes=size,member=member,gzip=True,
                encoding='gzip',compressed_member_sha256=compressed,compressed_member_bytes=compressed_size,expected_returncode=1,
                profile=profile,roles=['control:'+name],observations=['retained-parser','rust','leanchecker','leanchecker-paranoid']))
        persistence=rows['failed-persistence-does-not-promote-head'];failed=persistence['result']
        require(failed.get('status')=='UNKNOWN' and failed.get('evidence_id') is None and
                failed.get('action_authorization')=='NONE' and failed.get('poisoned') is True and
                persistence.get('poisoned') is True and persistence.get('expected_head_unchanged') is True and
                persistence.get('subsequent_in_place_update_refused') is True and
                persistence.get('historical_orphan_receipt_allowed_only_after_genuine_kernel_acceptance') is True and
                failed.get('reason')=='injected chain persistence failure',
                'failed persistence promoted a head, exposed acceptance or retained a live speculative process')
        restoration=rows['cold-recovery-after-rejections-and-corruption-then-dependency-restoration']
        require(type(restoration.get('replayed_revisions')) is int and restoration['replayed_revisions']==1 and
                restoration.get('restored_semantic_index') is True and
                restoration.get('retained_unused_dag_bytes_allow_different_export_sha') is True,
                'cold recovery did not restore exact semantic dependency state')
        parent,_=_native_index(store,store.join(root,'fresh-restored'),binaries['indexer']['path'])
        initial=parent
        require(canonical(initial)==canonical(baseline_index), 'control restored baseline differs from complete lifecycle profile reference')
        require(first['partition']['actual_kernel_total']==initial['count'], 'first-parent control uses a different workload declaration universe')
        transitions=rows['real-dependency-edge-fallback-refresh-and-restore'].get('transitions')
        require(type(transitions) is list and len(transitions)==4, 'topology fallback/refresh controls incomplete')
        parent_id=parent_head=None
        for number,(transition,retained) in enumerate(zip(transitions,(False,True,False,True))):
            folder=store.join(root,'edge-transitions',str(number))
            current,index_config=_native_index(store,store.join(folder,'fresh-index'),binaries['indexer']['path'])
            result=transition['result']
            validate_result_profile(result,profile,baseline_index['count'])
            if parent_id is None:
                parent_id=result.get('previous_evidence')
                require(hexid(parent_id), 'first topology predecessor identity missing')
            proof=validate_partition(result,parent,current,parent_id)
            recorded=transition.get('partition')
            require(type(recorded) is dict and set(recorded)==PARTITION_FIELDS and
                    canonical(recorded)==canonical({key:proof[key] for key in PARTITION_FIELDS}),
                    'topology recorded partition differs from independent SCC/prefix/dependency replay')
            require(result.get('typed_update',{}).get('retained_graph_used') is retained,
                    'topology fallback/retained refresh pattern differs')
            native=result.get('native_kernel_report',{})
            require(native.get('status')=='checked' and type(native.get('code')) is int and native['code']==0 and
                    native.get('kernel')=='sokonanoda_real_selected_declaration_check' and
                    type(native.get('checked')) is int and native['checked']==proof['actual_kernel_checked'] and
                    type(native.get('total_declarations')) is int and native['total_declarations']==current['count'],
                    'topology actual retained-kernel work differs from independent selected partition')
            link=result.get('revision_chain',{})
            require(type(link.get('revision')) is int and link['revision']==number+3 and
                    link.get('parent_evidence')==parent_id and hexid(link.get('head_id')) and
                    hexid(link.get('parent_head')) and hexid(link.get('source_capture_id')),
                    'topology revision/evidence chain linkage differs')
            if parent_head is not None:
                require(link['parent_head']==parent_head, 'topology substituted immediate predecessor head')
            oracle=transition['fresh_rust'];_outputs(store,oracle,0)
            require(len(oracle['command'])==2 and oracle['command'][0]==binaries['full_checker']['path'],
                    'topology fresh Rust command differs from measured kernel')
            full_config=_configuration(loads(store.saved(oracle['command'][1])))
            require(canonical(full_config)==canonical(index_config), 'topology native index and full kernel checked different inputs')
            parent,parent_id,parent_head=current,result['evidence_id'],link['head_id']
        require(canonical(parent)==canonical(initial), 'topology restore did not recover initial complete semantic index')
        results[profile]=dict(required_controls=32,actual_controls=32,exact_names=True,
            summary_sha256=descriptors[summary_member]['uncompressed_sha256'],kernel_negative_inputs=2,
            independently_replayed_topology_transitions=4,independent_scc_and_decision_origin_checks=True,
            failed_persistence_did_not_promote=True,cold_semantic_restoration=True,
            first_topology_parent_scope='identifier and all decision origins; prior step2 receipt absent from compact control artifact')
    return dict(status='PASS_INDEPENDENT_32_CONTROL_EVIDENCE',qualified=not smoke,profiles=results,
                required_controls=list(names),negative_inputs=negative_inputs,historical_hmac_reauthenticated=False,
                scope='Exact source-defined32 control names, compressed report identities, observed process outputs, exact rejected inputs, independent topology SCC/selected-set/decision-origin checks; no private-key HMAC reauthentication.')
