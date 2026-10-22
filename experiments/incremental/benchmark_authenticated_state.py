#!/usr/bin/env python3
"""Three-arm actual lifecycle economics for authenticated export-state receipts.

Full export witnesses and independent indexes are prepared outside the primary
intervals. Each arm then runs without interleaved oracles: production genesis,
all source-owned updates and close, or fresh Rust at every identical input.
State IDs remain construction identities, never counterfeit export hashes.
"""
import argparse
import copy
import fcntl
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

from authenticated_state import (StateChainSession, STATE_ACCEPTANCE, STATE_CHAIN,
    STATE_GENESIS, STATE_REPRESENTATION, STATE_TRANSITION)
from benchmark_revision_chain import (REPO, archive_blob, archive_descriptor,
    audit_chain_receipt, compact_directory, full_kernel, hexid, references,
    require, sequence_sample, source_directories, source_manifest,
    strict_object, uninterrupted_direct, validate_link)
from engine import cpu_time
from producer_delta import reconstruct_index_patch
from qualify_delta import (audit_partition, canonical, configuration, digest,
    file_hash, fresh_index, independent_partition, paired_economics, safe,
    sealed_snapshot, write)
from revision_chain import RevisionChainSession

SCHEMA = 'mathgraph.authenticated-export-state-economics.v1'
ARMS = ('state', 'full_export', 'direct')


def new_session(args, root, workloads, kind):
    cls = StateChainSession if kind == 'state' else RevisionChainSession
    return cls(root=root, workloads=workloads, producer=args.producer,
        checker=args.checker, indexer=args.indexer, index_session=args.index_session,
        authority_key=args.authority_key, retained_checker=args.retained_checker)


def compact_result(result, expected, source_root, kind):
    counts = expected['counts']
    report = result.get('native_kernel_report', {})
    observed_kernel = {name:report.get(name) for name in ('status','code','checked','total_declarations')}
    expected_kernel = dict(status='checked',code=0,checked=counts['rechecked'],total_declarations=counts['total'])
    require(result.get('status') == 'VERIFIED' and canonical(result.get('counts')) == canonical(counts) and
        source_root == expected['source_root'] and
        result.get('representation', {}).get('export_bytes') == expected['snapshot']['bytes'] and
        canonical(observed_kernel) == canonical(expected_kernel),
        'actual production result differs from independently checked obligations/input')
    if kind == 'state':
        require(hexid(result.get('state_id')) and result.get('export_sha256') is None and
            all(type(result['representation'].get(name)) is int and result['representation'][name] == 0 for name in (
                'full_export_bytes_materialized', 'full_export_bytes_hashed',
                'full_successor_bytes_read', 'full_export_disk_bytes_written')),
            'authenticated state acquired a full-export identity or full-export work')
    else:
        require(result.get('export_sha256') == expected['snapshot']['sha256'],
            'full-export control checked a different actual input')
    fields = ('status', 'evidence_id', 'previous_evidence', 'export_sha256',
        'revision_chain', 'counts', 'native_kernel_report', 'producer_provenance',
        'representation', 'timings')
    record = {field: copy.deepcopy(result[field]) for field in fields}
    if kind == 'state':
        record['state_id'] = result['state_id']
    record['source_root'] = source_root
    return record


def audit_state(root, result, parent_index, current_index, key, step,
                parent_source_root, parent_state, genesis):
    """Independent read-only issuer/object/full-index audit, outside timing.

    This does not call the mutable state's acceptance validator or reuse engine.
    The historical HMAC key is available only to this live qualification audit.
    Public replay checks object bytes and this observed-key witness separately.
    """
    cache = Path(root) / 'cache'
    def raw(category, identity, suffix='.json'):
        require(hexid(identity), 'malformed audited object address')
        data = (cache / category / (identity + suffix)).read_bytes()
        require(hashlib.sha256(data).hexdigest() == identity, 'audited state object corruption: ' + category)
        return data
    def obj(category, identity):
        return json.loads(raw(category, identity), object_pairs_hook=strict_object)
    def auth(category, identity, schema):
        value = obj(category, identity)
        require(set(value) == {'payload', 'hmac_sha256'} and hexid(value['hmac_sha256']) and
            value['payload'].get('schema') == schema and
            hmac.compare_digest(value['hmac_sha256'],
                hmac.new(key, canonical(value['payload']), hashlib.sha256).hexdigest()),
            'independent state HMAC/domain audit failed')
        return value['payload']
    receipt = auth('records', result['evidence_id'], STATE_ACCEPTANCE)
    expected_selected, expected_reused = independent_partition(parent_index, current_index)
    witness = receipt['identity']
    require(set(witness) == {'wire', 'value'} and witness['wire'] in ('baseline_patch_v1', 'full_index_v1'),
        'unsupported state index witness')
    rebuilt = (reconstruct_index_patch(parent_index, witness['value'])
               if witness['wire'] == 'baseline_patch_v1' else witness['value'])
    require(canonical(rebuilt) == canonical(current_index) and
        set(receipt) == {'schema', 'status', 'state_id', 'parent_state_id', 'previous_evidence',
            'producer_provenance', 'identity', 'obligation_count', 'checked_indices'} and
        receipt['status'] == 'VERIFIED' and receipt['state_id'] == result['state_id'] and
        receipt['parent_state_id'] == parent_state and
        receipt['previous_evidence'] == result['previous_evidence'] and
        receipt['obligation_count'] == current_index['count'] and
        receipt['checked_indices'] == expected_selected and
        canonical(receipt['producer_provenance']) == canonical(result['producer_provenance']),
        'issued state receipt differs from independent full-index partition')
    representation = obj('representations', result['state_id'])
    require(set(representation) == {'schema', 'genesis_id', 'genesis_export_sha256',
        'parent_state_id', 'parent_evidence_id', 'delta_sha256', 'transition_id', 'source_root',
        'policy_sha256', 'revision', 'export_bytes'}, 'ambiguous state representation')
    transition = auth('transitions', representation['transition_id'], STATE_TRANSITION)
    delta = raw('deltas', representation['delta_sha256'], '.ndjson')
    link = result['revision_chain']
    head = auth('chain', link['head_id'], STATE_CHAIN)
    capture = obj('source-captures', link['source_capture_id'])
    require(representation['schema'] == STATE_REPRESENTATION and
        representation['genesis_id'] == genesis['head_id'] and
        representation['genesis_export_sha256'] == genesis['export_sha256'] and
        representation['parent_state_id'] == parent_state and
        representation['parent_evidence_id'] == result['previous_evidence'] and
        representation['source_root'] == step['source_root'] and
        representation['policy_sha256'] == digest(result['producer_provenance']) and
        representation['revision'] == link['revision'] and
        representation['export_bytes'] == result['representation']['export_bytes'] and
        transition['base_state_id'] == parent_state and
        transition['base_evidence_id'] == result['previous_evidence'] and
        transition['baseline_source_root'] == parent_source_root and
        transition['source_root'] == step['source_root'] and
        transition['delta_sha256'] == representation['delta_sha256'] and
        canonical(transition['provenance']) == canonical(result['producer_provenance']) and
        head['evidence_id'] == result['evidence_id'] and head['state_id'] == result['state_id'] and
        head['previous_evidence'] == result['previous_evidence'] and
        head['previous_head'] == link['parent_head'] and head['revision'] == link['revision'] and
        head['source_capture_id'] == link['source_capture_id'] and
        head['source_root'] == step['source_root'] and
        head['delta_sha256'] == representation['delta_sha256'] and
        head['policy_sha256'] == digest(result['producer_provenance']) and
        capture['schema'] == 'mathgraph.lean-complete-source-capture.v1' and
        canonical(capture['sources']) == canonical(step['sources']) and
        canonical(capture['patch']) == canonical(step['patch']) and
        capture['claimed_names'] == step['claimed_names'],
        'authenticated state receipt/representation/transition/head/source linkage differs')
    return dict(issuer_hmac_valid=True, all_content_addresses_valid=True,
        full_index_and_partition_exact=True, checked_indices=expected_selected,
        reused_indices=expected_reused, identity_witnesses_checked=current_index['count'],
        state_id=result['state_id'], receipt_sha256=result['evidence_id'],
        delta_sha256=representation['delta_sha256'], delta_bytes=len(delta),
        transition_id=representation['transition_id'], head_id=link['head_id'],
        index_sha256=digest(current_index),
        scope='Actual-key HMAC/content audit with independently rebuilt full index and partition; no new acceptance authority.')


def state_genesis(session):
    raw = session._object('representations', session.state_id, '.json')
    value = json.loads(raw, object_pairs_hook=strict_object)
    require(value == dict(schema=STATE_GENESIS, genesis_id=session.genesis_head,
        genesis_evidence_id=session.base_id, export_sha256=session.export_pins['baseline'],
        policy_sha256=digest(session.delta_provenance)), 'state genesis binding mismatch')
    return dict(head_id=session.head_id, evidence_id=session.base_id, state_id=session.state_id,
        export_sha256=session.export_pins['baseline'], source_root=session.source_root)


def state_witness(args, profile, workloads, plan, refs, legacy):
    directory = args.out / 'witness-state' / profile
    session = new_session(args, directory / 'session', workloads, 'state')
    record = dict(completed=False, steps=[])
    try:
        record['ready'] = session.start()
        record['genesis'] = state_genesis(session)
        parent_index, parent_state = refs[0], session.state_id
        parent_source = session.source_root
        manifest = json.loads((workloads / 'manifest.json').read_bytes())
        for revision, (step, expected) in enumerate(zip(plan, legacy['steps']), 1):
            parent_head, parent_evidence = session.head_id, session.base_id
            result = session.apply(step['source_dir'], tuple(step['patch']), step['claimed_names'])
            validate_link(result, parent_head, parent_evidence, revision)
            require(canonical(result['counts']) == canonical(expected['counts']),
                'state/full-export measured work counts disagree')
            partition = audit_partition(result, parent_index, refs[step['state']])
            require(partition == expected['partition_audit'], 'state/full-export selected sets or witnesses disagree')
            require(canonical(session.old['index']) == canonical(refs[step['state']]), 'state live full index differs')
            exported = session.materialize_current()
            require(exported['export_sha256'] == expected['snapshot']['sha256'] and
                exported['export_bytes'] == expected['snapshot']['bytes'],
                'explicit state export differs from qualified full-export path')
            direct = full_kernel(args.full_checker, exported['path'], directory / ('revision-%03d' % revision) / 'rust')
            audit = audit_state(session.root, result, parent_index, refs[step['state']],
                args.authority_key.read_bytes(), step, parent_source, parent_state, record['genesis'])
            require(audit['delta_sha256'] == expected['receipt_audit']['delta_sha256'],
                'state/full-export paths consumed different actual producer deltas')
            additional = {}
            if revision <= 4:
                for name in ('leanchecker', 'leanchecker-paranoid'):
                    additional[name] = full_kernel(manifest['tools'][name]['path'], exported['path'],
                        directory / ('revision-%03d' % revision) / name, cpp=True)
            raw_result = directory / ('revision-%03d' % revision) / 'result.json'
            write(raw_result, result)
            compressed = archive_blob(raw_result, args.out);raw_result.unlink()
            record['steps'].append(dict(revision=revision, state_id=session.state_id,
                head_id=session.head_id, evidence_id=session.base_id, counts=result['counts'],
                snapshot=exported, direct_rust=direct, additional_oracles=additional,
                independent_audit=audit, result_witness=compressed,
                compressed_files=compact_directory(directory / ('revision-%03d' % revision), args.out)))
            parent_index, parent_state, parent_source = refs[step['state']], session.state_id, session.source_root
            write(directory / 'partial.json', record)
        head, evidence, state_id = session.head_id, session.base_id, session.state_id
        session.close()
        tick = time.perf_counter()
        with new_session(args, directory / 'session', workloads, 'state') as cold:
            ready = cold.start(expected_head=head)
            require(cold.head_id == head and cold.base_id == evidence and cold.state_id == state_id and
                cold.revision == len(plan) and canonical(cold.old['index']) == canonical(parent_index),
                'cold state replay changed accepted evidence/index')
            replay = dict(passed=True, ready=ready, expected_head=head, actual_head=cold.head_id,
                state_id=cold.state_id, wall_seconds=time.perf_counter()-tick)
        record.update(completed=True, cold_replay=replay,
            compressed_session_files=compact_directory(directory / 'session', args.out))
        write(directory / 'summary.json', record)
        return record
    finally:
        session.close()


def timed_candidate(args, workloads, directory, plan, witness, kind):
    session, closed = None, False
    observations = []
    wall_tick, cpu_tick = time.perf_counter(), cpu_time()
    try:
        session = new_session(args, directory / 'session', workloads, kind)
        tick, ctick = time.perf_counter(), session.cpu_time()
        ready = session.start()
        setup_wall, setup_cpu = time.perf_counter()-wall_tick, session.cpu_time()-cpu_tick
        require(session.baseline_result['status'] == 'VERIFIED' and
            session.old['export_sha256'] == witness['genesis']['export_sha256'],
            'timed genesis differs from verified input')
        genesis = dict(head_id=session.head_id, evidence_id=session.base_id,
            export_sha256=session.old['export_sha256'], source_root=session.source_root, ready=ready)
        if kind == 'state':genesis['state_id'] = session.state_id
        for revision, (step, expected) in enumerate(zip(plan, witness['steps']), 1):
            parent_head, parent_evidence = session.head_id, session.base_id
            tick, ctick = time.perf_counter(), session.cpu_time()
            result = session.apply(step['source_dir'], tuple(step['patch']), step['claimed_names'])
            elapsed, cputime = time.perf_counter()-tick, session.cpu_time()-ctick
            validate_link(result, parent_head, parent_evidence, revision)
            compact = compact_result(result, expected, session.source_root, kind)
            compact.update(revision=revision, apply_wall_seconds=elapsed, apply_cpu_seconds=cputime,
                memory=session.memory_observation())
            observations.append(compact)
            result = None
        final_head, final_evidence = session.head_id, session.base_id
        memory = session.memory_observation()
        tick, ctick = time.perf_counter(), session.cpu_time()
        session.close();closed=True
        close_wall, close_cpu = time.perf_counter()-tick, session.cpu_time()-ctick
        wall_seconds, cpu_seconds = time.perf_counter()-wall_tick, session.cpu_time()-cpu_tick
        return dict(completed=True, wall_seconds=wall_seconds, cpu_seconds=cpu_seconds,
            setup_wall_seconds=setup_wall, setup_cpu_seconds=setup_cpu,
            close_wall_seconds=close_wall, close_cpu_seconds=close_cpu,
            genesis=genesis, steps=observations, final_head=final_head,
            final_evidence=final_evidence, memory=memory,
            scope='Uninterrupted constructor/start, all real source-owned applies and supported close; '
                'compact recording and memory samples included, no full-index digest, export materialization, '
                'independent oracle, HMAC audit, compression or evidence writes between production APIs.')
    finally:
        if session is not None and not closed:session.close()


def prepare_inputs(args, directory, legacy):
    descriptors, prepared, witnesses = [], {}, {}
    blob = legacy['genesis']['baseline_witness'];witnesses[blob['uncompressed_sha256']] = blob
    for step in legacy['steps']:
        if step.get('export_witness'):
            blob=step['export_witness'];witnesses[blob['uncompressed_sha256']] = blob
    inputs = [legacy['genesis']['export_sha256']] + [s['snapshot']['sha256'] for s in legacy['steps']]
    try:
        for identity in dict.fromkeys(inputs):
            blob=witnesses[identity]
            require(file_hash(blob['path']) == blob['sha256'], 'direct input archive changed')
            fd=os.memfd_create('state-economics-direct',os.MFD_ALLOW_SEALING);descriptors.append(fd)
            with gzip.open(blob['path'],'rb') as stream:
                while chunk:=stream.read(1 << 20):
                    view=memoryview(chunk)
                    while view:n=os.write(fd,view);view=view[n:]
            fcntl.fcntl(fd,getattr(fcntl,'F_ADD_SEALS',1033),15)
            path=Path('/proc')/str(os.getpid())/'fd'/str(fd)
            snapshot=sealed_snapshot(path)
            require(snapshot['sha256']==identity and snapshot['bytes']==blob['uncompressed_bytes'],
                'direct input does not match exact independently checked complete export')
            config=directory/'configs'/(identity+'.json');write(config,configuration(path))
            prepared[identity]=dict(snapshot=snapshot,config=config,config_sha256=file_hash(config))
        return inputs,prepared,descriptors
    except Exception:
        for fd in descriptors:os.close(fd)
        raise


def audit_timed(args, root, kind, observed, plan, refs, legacy):
    parent_index=refs[0];parent_source=observed['genesis']['source_root']
    parent_state=observed['genesis'].get('state_id')
    if kind=='state':
        raw=(Path(root)/'cache'/'representations'/(parent_state+'.json')).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==parent_state and
            json.loads(raw,object_pairs_hook=strict_object)==dict(schema=STATE_GENESIS,
                genesis_id=observed['genesis']['head_id'],
                genesis_evidence_id=observed['genesis']['evidence_id'],
                export_sha256=observed['genesis']['export_sha256'],
                policy_sha256=digest(observed['steps'][0]['producer_provenance'])),
            'timed state genesis construction is not bound to admitted evidence and policy')
    for step, actual, expected in zip(plan,observed['steps'],legacy['steps']):
        if kind=='state':
            audit=audit_state(root,actual,parent_index,refs[step['state']],args.authority_key.read_bytes(),
                step,parent_source,parent_state,observed['genesis'])
            require(audit['delta_sha256']==expected['receipt_audit']['delta_sha256'],
                'timed state consumed a different producer delta from the complete input witness')
            parent_state=actual['state_id']
        else:
            audit=audit_chain_receipt(root,actual,parent_index,refs[step['state']],
                args.authority_key.read_bytes(),expected['partition_audit'],step,parent_source)
        actual['independent_audit']=audit
        parent_index,parent_source=refs[step['state']],step['source_root']


def primary_pair(args, profile, workloads, repetition, plan, refs, legacy):
    directory=args.out/'primary'/profile/('pair-'+str(repetition))
    directory.mkdir(parents=True,exist_ok=True)
    inputs,prepared,fds=prepare_inputs(args,directory/'direct',legacy)
    # Rotate all three arms; each retains a single uninterrupted lifetime.
    order=list(ARMS[repetition%3:]+ARMS[:repetition%3])
    record=dict(repetition=repetition,order=order,completed=False)
    try:
        for kind in order:
            if kind=='direct':
                record[kind],outputs=uninterrupted_direct(args,directory/kind,inputs,prepared)
            else:
                record[kind]=timed_candidate(args,workloads,directory/kind,plan,legacy,kind)
        # No work below enters any measured primary lifecycle interval.
        for kind in ('state','full_export'):
            audit_timed(args,directory/kind/'session',kind,record[kind],plan,refs,legacy)
            record[kind]['compressed_session_files']=compact_directory(directory/kind/'session',args.out)
        for process,(stdout,stderr) in zip(record['direct']['commands'],outputs):
            folder=directory/'direct'/('revision-%03d'%process['revision'])
            for name,raw in (('stdout',stdout),('stderr',stderr)):
                path=folder/('process.'+name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                process[name+'_path']=str(path);process[name+'_sha256']=hashlib.sha256(raw).hexdigest()
            write(folder/'process.json',process)
        record['completed']=True;write(directory/'summary.json',record)
        return record
    finally:
        for fd in fds:os.close(fd)


def economics(pairs, candidate, comparator, field, *, seed):
    values=[dict(apply_wall_seconds=p[candidate][field],direct_wall_seconds=p[comparator][field]) for p in pairs]
    result=paired_economics(values,seed=seed)
    result.update(candidate=candidate,comparator=comparator,measurement=field,setup_in_timed_update=True,
        reduction_percent=100*(1-result['median_ratio']),speedup=1/result['median_ratio'],
        scope='Paired uninterrupted complete lifecycle: production constructor/start, every source-owned update, '
            'and supported close; direct arm is fresh Rust at genesis and every identical actual input.',
        candidate_scope=candidate,comparator_scope=comparator)
    if len(pairs)<5:
        result.update(observed_status=result['status'],status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS',passed=False)
    return result


def manifests():
    value=source_manifest()
    for path in (REPO/'.github/workflows').glob('*incremental*.yml'):
        value[str(path.relative_to(REPO))]=file_hash(path)
    return value


def run(args):
    require(not args.out.exists() or not any(args.out.iterdir()),'use fresh output directory')
    args.out.mkdir(parents=True,exist_ok=True)
    require(args.authority_key.is_file() and len(args.authority_key.read_bytes())==32 and
        args.out not in args.authority_key.parents,'private 32-byte issuer key must be outside evidence')
    status=subprocess.check_output(['git','status','--porcelain','--','src','experiments/incremental','.github/workflows'],cwd=REPO,text=True)
    report=dict(schema=SCHEMA,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        source_tracked_clean=not bool(status.strip()),source_git_status=status,source_sha256=manifests(),
        binary_sha256={},repetitions=args.repetitions,cycles=args.cycles,requested_profiles=args.profiles,
        completed=False,correctness_passed=False,qualified=False,profiles={},host=list(platform.uname()),
        measurement_policy=dict(primary='Uninterrupted production constructor/start → all source capture, '
            'producer, authentication, identity update, selected checking, persistence → supported close.',
            direct='Fresh Rust at genesis and each identical complete input; preparation outside timing favors direct.',
            order='Rotating three-arm order; warm OS file caches, same host.',
            witness='Independent complete-input/index/oracle and actual-key receipt audits outside all primary intervals.',
            memory='Post-phase procfs RSS and cumulative VmHWM; not aggregate or exact phase peaks.',
            asymptotic='Full index reconstruction/copy, applicability loops and cold export admission remain O(N); '
                'only warm full-export materialization, file hashing and readback are removed.'),
        trust_boundary=dict(identity='Authenticated state construction CAS, explicitly separate from exact-export SHA.',
            authority='Existing private HMAC issuer and source-owned transition policy; unchanged genuine Rust kernel and reuse predicate.',
            export='Explicit O(N) materialization is independently compared to qualified complete-export path; no full-export SHA claimed at warm acceptance.'),
        phase_semantics=dict(materialization_and_hash_seconds=dict(
            state='Delta-only JSON framing, names and immutable recipe transition; no full export is materialized or hashed.',
            full_export='Qualified complete export composition, hashing and sealed snapshot creation.'),
            persistence_seconds='Receipt reconstruction/authentication, CAS writes and chain promotion; includes nested chain_promotion_seconds, never sum them.',
            cpu='Adapter/completed-child CPU plus procfs live-daemon ticks; SC_CLK_TCK granularity applies.',
            memory='Per-process post-phase RSS and cumulative VmHWM observations; no sum of process peaks.'))
    for name in ('producer','checker','retained_checker','indexer','index_session','full_checker'):
        path=getattr(args,name);report['binary_sha256'][name]=dict(path=str(path),sha256=file_hash(path))
    def flush():write(args.out/'summary.json',report)
    flush()
    try:
        for profile in args.profiles:
            workloads=getattr(args,profile+'_workloads');plan=source_directories(args,profile,workloads)
            refs,reference_records=references(args,profile,workloads,plan)
            manifest=json.loads((workloads/'manifest.json').read_bytes())
            item=dict(references=reference_records,pairs=[],workload_manifest_sha256=file_hash(workloads/'manifest.json'),
                workload_profile=manifest.get('profile','original-v1'))
            report['profiles'][profile]=item
            for name in ('lean','leanchecker','leanchecker-paranoid'):
                path=manifest['tools'][name]['path']
                report['binary_sha256'][profile+':'+name]=dict(path=path,sha256=file_hash(path))
            flush()
            # Reuse the qualified full-export witness/oracle machinery once,
            # rather than repeating expensive independent oracles in each timer.
            legacy=sequence_sample(args,profile,workloads,0,plan,refs,set(),lambda value:None)
            for step in legacy['steps']:
                partition=step['partition_audit'];n=partition['actual_kernel_checked'];total=partition['actual_kernel_total']
                step['counts']=dict(total=total,scheduled=n,rechecked=n,reused=total-n,invalidated=n)
                # Legacy audit does not publish this convenience link, but the
                # exact CAS representation is independent evidence for it.
                root=args.out/'profiles'/profile/'pair-0'/'session'/'cache'
                envelope=json.loads((root/'records'/(step['evidence_id']+'.json')).read_bytes())
                rid=envelope['payload']['delta_representation']
                representation=json.loads((root/'representations'/(rid+'.json')).read_bytes())
                step['receipt_audit']['delta_sha256']=representation['delta_sha256']
            item['full_export_witness']=legacy;flush()
            item['state_witness']=state_witness(args,profile,workloads,plan,refs,legacy);flush()
            for repetition in range(args.repetitions):
                item['pairs'].append(primary_pair(args,profile,workloads,repetition,plan,refs,legacy));flush()
                print(json.dumps(dict(profile=profile,repetition=repetition,completed=True,
                    wall_seconds={arm:item['pairs'][-1][arm]['wall_seconds'] for arm in ARMS})),flush=True)
            item['economics']={}
            for i,(candidate,comparator) in enumerate((('state','direct'),('state','full_export'),('full_export','direct'))):
                for field in ('wall_seconds','cpu_seconds'):
                    item['economics'][candidate+'_vs_'+comparator+'_'+field]=economics(item['pairs'],candidate,comparator,field,seed=20261024+i)
            item['warm_edit_economics']={}
            for variant in ('early-definition','unrelated-definition','restore-early-definition','restore-unrelated-definition'):
                positions=[i for i,step in enumerate(plan) if step['name']==variant]
                series=[]
                for pair in item['pairs']:
                    series.append(dict(state=sum(pair['state']['steps'][i]['apply_wall_seconds'] for i in positions),
                        full_export=sum(pair['full_export']['steps'][i]['apply_wall_seconds'] for i in positions),
                        direct=sum(pair['direct']['commands'][i+1]['wall_seconds'] for i in positions)))
                item['warm_edit_economics'][variant]={}
                for comparator in ('direct','full_export'):
                    values=[dict(apply_wall_seconds=p['state'],direct_wall_seconds=p[comparator]) for p in series]
                    value=paired_economics(values,seed=20261030)
                    value.update(updates_per_pair=len(positions),reduction_percent=100*(1-value['median_ratio']),speedup=1/value['median_ratio'],
                        scope='Paired sums of '+str(len(positions))+' actual warm production applies of this edit kind; initialization and close excluded.',
                        comparator='Fresh direct Rust on each identical export' if comparator=='direct' else
                            'Previously qualified full-export revision adapter on each identical update',
                        state_median_seconds_per_update=statistics.median(p['state'] for p in series)/len(positions),
                        comparator_median_seconds_per_update=statistics.median(p[comparator] for p in series)/len(positions))
                    if args.repetitions<5:value.update(observed_status=value['status'],status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS',passed=False)
                    item['warm_edit_economics'][variant]['state_vs_'+comparator]=value
            flush()
        for path,identity in report['source_sha256'].items():require(file_hash(REPO/path)==identity,'measured source drift: '+path)
        for name,record in report['binary_sha256'].items():require(file_hash(record['path'])==record['sha256'],'measured executable drift: '+name)
        correctness_qualified=(not args.smoke and args.repetitions==5 and args.cycles==10 and
            set(args.profiles)=={'original','expanded'} and report['source_tracked_clean'])
        economic_pass=all(profile['economics'][name]['passed'] is True
            for profile in report['profiles'].values()
            for name in ('state_vs_direct_wall_seconds','state_vs_full_export_wall_seconds'))
        report.update(completed=True,correctness_passed=True,source_and_binary_stable=True,
            qualified=correctness_qualified,correctness_qualified=correctness_qualified,
            qualification_status='CORRECTNESS_QUALIFIED_BOUNDED' if correctness_qualified else 'SMOKE_CORRECTNESS_ONLY',
            economic_status=('QUALIFIED_SPEEDUP' if economic_pass else 'QUALIFIED_NEGATIVE_OR_INCONCLUSIVE')
                if correctness_qualified else 'SMOKE_OR_INCOMPLETE',
            qualified_field_scope='Backward-compatible alias of correctness_qualified; economic claims require economic_status and passed comparator metrics.')
        flush()
        write_markdown(args.out/'summary.md',report)
        print(json.dumps(dict(completed=True,qualified=report['qualified'],summary_sha256=file_hash(args.out/'summary.json'))),flush=True)
        return report
    except Exception as error:
        report['error']=repr(error);flush();raise


def write_markdown(path,report):
    lines=['# Authenticated export-state measurements','',
        'The primary interval includes constructor/start, every actual source-owned update and supported close. '
        'Direct fresh Rust checks genesis and all identical actual revision exports; its input preparation is outside timing. '
        'Independent materialization, full-index, kernel and receipt oracles run outside these intervals.','',
        '| Profile | Updates | State lifecycle, s | Full-export lifecycle, s | Direct Rust lifecycle, s | State / direct speedup | State / full-export speedup |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for profile,value in report['profiles'].items():
        pairs=value['pairs'];e=value['economics']
        lines.append(f"| {profile} | {4*report['cycles']} | "
            f"{statistics.median(p['state']['wall_seconds'] for p in pairs):.6f} | "
            f"{statistics.median(p['full_export']['wall_seconds'] for p in pairs):.6f} | "
            f"{statistics.median(p['direct']['wall_seconds'] for p in pairs):.6f} | "
            f"{e['state_vs_direct_wall_seconds']['speedup']:.4f}× | "
            f"{e['state_vs_full_export_wall_seconds']['speedup']:.4f}× |")
    lines+=['','| Profile / warm edit | State per update, s | Direct Rust per update, s | Speedup |',
        '| --- | ---: | ---: | ---: |']
    for profile,value in report['profiles'].items():
        for variant in ('early-definition','unrelated-definition'):
            e=value['warm_edit_economics'][variant]['state_vs_direct']
            lines.append(f"| {profile} / {variant} | {e['state_median_seconds_per_update']:.6f} | "
                f"{e['comparator_median_seconds_per_update']:.6f} | {e['speedup']:.4f}× |")
    lines+=['', 'Correctness qualification: '+report['qualification_status']+'. Economic status: '+report['economic_status']+'.',
        '', 'These are same-host warm-cache observations. Cold initialization and expected-head replay are recorded separately. '
        'Post-phase RSS/VmHWM are observations, not aggregate peaks. The state receipt is an authenticated construction identity, '
        'not a full-export SHA. Full typed-index/applicability loops and cold admission remain O(N); no asymptotic claim is made.']
    Path(path).write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('original-workloads','expanded-workloads','producer','checker','retained-checker',
        'indexer','index-session','full-checker','authority-key','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--profiles',nargs='+',choices=('original','expanded'),default=['original','expanded'])
    parser.add_argument('--repetitions',type=int,default=5)
    parser.add_argument('--cycles',type=int,default=10)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    for name in ('original_workloads','expanded_workloads','producer','checker','retained_checker',
        'indexer','index_session','full_checker','authority_key','out'):
        setattr(args,name,getattr(args,name).resolve())
    require(args.repetitions>0 and args.cycles>0 and len(set(args.profiles))==len(args.profiles),'positive counts and unique profiles required')
    if not args.smoke:require(args.repetitions==5 and args.cycles==10 and set(args.profiles)=={'original','expanded'},'qualification requires five forty-update pairs on both profiles')
    run(args)


if __name__=='__main__':main()
