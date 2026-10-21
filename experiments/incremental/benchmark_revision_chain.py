#!/usr/bin/env python3
"""Measured authenticated revision streams, with exact full-checker comparators.

Primary paired arms run uninterrupted constructor/start, all revisions, and
supported close, versus fresh full Rust at genesis and every identical revision.
A separate interleaved arm establishes full-index/kernel/receipt evidence and
retains observed API component sums. No metric is extrapolated from one update.
"""
import argparse
import copy
import fcntl
import gzip
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

from build_workloads import EDITS
from engine import cpu_time as adapter_cpu_time
from producer_delta import JsonProcess, SPARSE_ACCEPTANCE, sources_at, lean_sources, reconstruct_index_patch
from qualify_delta import (audit_partition, canonical, command_run, configuration,
                           digest, file_hash, fresh_index, paired_economics,
                           safe, sealed_snapshot, write)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCHEMA = 'mathgraph.authenticated-revision-chain-lifecycle.v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hexid(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def revision_plan(sources, cycles):
    require(type(cycles) is int and cycles > 0, 'cycles must be a positive integer')
    current = dict(sources)
    plan = []
    for cycle in range(cycles):
        for state, variant, restore in ((1, 'early-definition', False),
                                        (2, 'unrelated-definition', False),
                                        (3, 'early-definition', True),
                                        (0, 'unrelated-definition', True)):
            name, before, after = EDITS[variant]
            if restore:
                before, after = after, before
            require(name in current and current[name].count(before) == 1,
                    'revision source patch is ambiguous or does not name its immediate parent')
            current = dict(current)
            current[name] = current[name].replace(before, after)
            plan.append(dict(cycle=cycle, state=state, name=('restore-' if restore else '') + variant,
                             patch=(name, before, after), sources=current,
                             claimed_names=['IncrementalWorkload.' + ('early' if variant == 'early-definition' else 'unrelated')]))
        require(current == sources, 'a complete source cycle did not restore the genesis source')
    return plan


def lifecycle_components(setup, applies, close, direct_baseline, directs):
    require(len(applies) == len(directs) and len(applies) > 0,
            'each accepted revision requires its own direct full Rust comparator')
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0
                for v in [setup, close, direct_baseline] + applies + directs),
            'invalid actual lifetime component')
    return dict(setup_wall_seconds=setup, apply_wall_seconds=applies,
                close_wall_seconds=close, direct_genesis_wall_seconds=direct_baseline,
                direct_revision_wall_seconds=directs, accepted_revisions=len(applies),
                api_component_sum_wall_seconds=setup + sum(applies) + close,
                direct_full_rust_component_sum_wall_seconds=direct_baseline + sum(directs),
                scope='Observed constructor/start + every production apply + supported close API intervals; '
                      'intervening independent oracles and harness evidence packaging are excluded. '
                      'Direct comparator is a fresh full Rust command at genesis and every exact accepted revision.')


def lifecycle_cpu_components(setup, applies, close, direct_baseline, directs):
    observed = lifecycle_components(setup, applies, close, direct_baseline, directs)
    return dict(setup_cpu_seconds=setup, apply_cpu_seconds=applies, close_cpu_seconds=close,
                direct_genesis_cpu_seconds=direct_baseline, direct_revision_cpu_seconds=directs,
                api_component_sum_cpu_seconds=observed['api_component_sum_wall_seconds'],
                direct_full_rust_component_sum_cpu_seconds=observed['direct_full_rust_component_sum_wall_seconds'],
                scope='Adapter + completed-child resource CPU + live producer/index/kernel procfs CPU; '
                      'SC_CLK_TCK granularity applies to live daemons. Separately summed observed API intervals; '
                      'direct full Rust uses completed-child CPU per actual fresh command.')


def validate_link(result, parent_head, parent_evidence, revision):
    require(result.get('status') == 'VERIFIED' and hexid(result.get('evidence_id')),
            'revision did not produce actual accepted evidence')
    link = result.get('revision_chain')
    require(type(link) is dict and type(link.get('revision')) is int and
            link['revision'] == revision and link.get('parent_head') == parent_head and
            link.get('parent_evidence') == parent_evidence and
            result.get('previous_evidence') == parent_evidence and
            hexid(link.get('head_id')) and hexid(link.get('source_capture_id')),
            'revision head, immediate parent, order, or source capture is not bound')
    return link


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate field in independently audited JSON')
        result[key] = value
    return result


def audit_chain_receipt(root, result, parent_index, current_index, key, partition, step, parent_source_root):
    """Read actual issued bytes; replay applicability from independent full indexes.

    This is evidence checking, not an issuer. The independently built full index
    must agree with both the sparse receipt reconstruction and selected set.
    """
    cache = Path(root) / 'cache'
    def read(category, identity, suffix):
        require(hexid(identity), 'invalid audited content address')
        path = cache / category / (identity + suffix)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == identity,
                'persisted chain content address mismatch: ' + category)
        return raw
    def auth(raw, schema):
        envelope = json.loads(raw, object_pairs_hook=strict_object)
        require(set(envelope) == {'payload', 'hmac_sha256'}, 'unexpected issuer envelope')
        payload = envelope['payload']
        require(payload.get('schema') == schema and type(envelope['hmac_sha256']) is str and
                hmac.compare_digest(envelope['hmac_sha256'], hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()),
                'independent chain issuer authentication failed')
        return payload
    raw = read('records', result['evidence_id'], '.json')
    accepted = auth(raw, SPARSE_ACCEPTANCE)
    restored = reconstruct_index_patch(parent_index, accepted['index_patch'])
    require(accepted['status'] == 'VERIFIED' and
            accepted['export_sha256'] == result['export_sha256'] and
            accepted['previous_evidence'] == result['previous_evidence'] and
            accepted['obligation_count'] == current_index['count'] and
            canonical(restored) == canonical(current_index) and
            accepted['checked_indices'] == partition['checked_indices'] and
            canonical(accepted['producer_provenance']) == canonical(result['producer_provenance']),
            'signed chain acceptance differs from independent full index/partition')
    representation = json.loads(read('representations', accepted['delta_representation'], '.json'),
                                object_pairs_hook=strict_object)
    require(representation['schema'] == 'mathgraph.lean-delta-representation.v1' and
            representation['export_sha256'] == result['export_sha256'] and
            representation['base_evidence_id'] == result['previous_evidence'],
            'chain representation names a different immediate parent/export')
    transition = auth(read('transitions', representation['transition_id'], '.json'),
                      'mathgraph.lean-source-owned-transition.v1')
    delta = read('deltas', representation['delta_sha256'], '.ndjson')
    require(transition['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
            transition['base_evidence_id'] == result['previous_evidence'] and
            transition['baseline_source_root'] == parent_source_root and
            transition['source_root'] == step['source_root'] and
            canonical(transition['provenance']) == canonical(result['producer_provenance']),
            'chain transition does not authenticate exact delta and immediate parent')
    link = result['revision_chain']
    head = auth(read('chain', link['head_id'], '.json'), 'mathgraph.lean-accepted-predecessor-chain.v1')
    capture = json.loads(read('source-captures', link['source_capture_id'], '.json'), object_pairs_hook=strict_object)
    require(head['evidence_id'] == result['evidence_id'] and head['revision'] == link['revision'] and
            head['previous_head'] == link['parent_head'] and head['previous_evidence'] == result['previous_evidence'] and
            head['source_capture_id'] == link['source_capture_id'] and
            head['source_root'] == step['source_root'] and head['export_sha256'] == result['export_sha256'] and
            head['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
            head['policy_sha256'] == digest(result['producer_provenance']) and
            capture['schema'] == 'mathgraph.lean-complete-source-capture.v1' and
            canonical(capture['sources']) == canonical(step['sources']) and
            canonical(capture['patch']) == canonical(step['patch']) and
            capture['claimed_names'] == step['claimed_names'],
            'authenticated chain head or complete source capture differs from actual planned transition')
    return dict(issuer_hmac_valid=True, all_content_addresses_valid=True,
                receipt_schema=SPARSE_ACCEPTANCE, receipt_bytes=len(raw), delta_bytes=len(delta),
                full_index_and_partition_exact=True, contains_complete_index=False,
                previous_evidence=accepted['previous_evidence'],
                receipt_sha256=result['evidence_id'],
                head_hmac_valid=True, complete_source_capture_exact=True, head_id=link['head_id'],
                source_capture_id=link['source_capture_id'],
                scope='Independent observed-key HMAC/content checks and full-index selected-set audit; no new acceptance authority.')


def archive_blob(path, out):
    """Deduplicate immutable evidence after timing, preserving original byte identity."""
    path, out = Path(path), Path(out)
    identity, size = file_hash(path), path.stat().st_size
    target = out / 'witnesses' / 'objects' / (identity + '.gz')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with path.open('rb') as source, target.open('wb') as destination:
            with gzip.GzipFile(filename='', fileobj=destination, mode='wb', mtime=0) as compressed:
                shutil.copyfileobj(source, compressed)
    return dict(path=str(target), artifact_relative_path=str(target.relative_to(out)),
                sha256=file_hash(target), bytes=target.stat().st_size, encoding='gzip',
                uncompressed_sha256=identity, uncompressed_bytes=size)


def archive_descriptor(record, previous=None):
    require(record.get('encoding') == 'gzip' and hexid(record.get('sha256')) and
            hexid(record.get('uncompressed_sha256')) and type(record.get('bytes')) is int and
            record['bytes'] > 0 and type(record.get('uncompressed_bytes')) is int and
            record['uncompressed_bytes'] >= 0, 'invalid exact-byte archive descriptor')
    descriptor = (record['sha256'], record['bytes'], record['uncompressed_sha256'], record['uncompressed_bytes'])
    require(previous is None or descriptor == previous, 'conflicting repeated exact-byte archive descriptor')
    return descriptor


def validate_export_coverage(actual_inputs, witnessed_inputs):
    require(actual_inputs and actual_inputs <= witnessed_inputs,
            'actual checked revision input lacks a validated complete-export witness')


def compact_directory(directory, out):
    records = []
    for path in sorted(Path(directory).rglob('*')):
        if not path.is_file() or path.stat().st_size < 512 * 1024:
            continue
        record = archive_blob(path, out)
        record['original_path'] = str(path)
        write(path.with_name(path.name + '.archive.json'), record)
        path.unlink()
        records.append(record)
    return records


def full_kernel(binary, export, directory, *, cpp=False):
    directory = Path(directory)
    config = directory / 'config.json'
    write(config, configuration(export))
    command = [binary, '--from-export', export] if cpp else [binary, config]
    record, _stdout = command_run(command, directory / 'process')
    require(record['returncode'] == 0 and record['timed_out'] is False,
            'fresh full kernel rejected or failed: ' + str(record))
    record.update(input_sha256=file_hash(export), input_bytes=Path(export).stat().st_size,
                  config_sha256=file_hash(config), config_path=str(config))
    write(directory / 'process.json', record)
    return record


def source_directories(args, profile, workloads):
    sources = sources_at(workloads / 'baseline' / 'source')
    plan = revision_plan(sources, args.cycles)
    for step in plan[:4]:
        directory = args.out / 'sources' / profile / str(step['state'])
        for name, text in step['sources'].items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
    for step in plan:
        step['source_dir'] = args.out / 'sources' / profile / str(step['state'])
        step['source_root'] = digest(step['sources'])
    write(args.out / 'sources' / profile / 'plan.json', [
        {key: value for key, value in step.items() if key != 'sources'} for step in plan])
    return plan


def references(args, profile, workloads, plan):
    """Establish four source-state identities from independent complete exports."""
    manifest = json.loads((workloads / 'manifest.json').read_bytes())
    directory = args.out / 'references' / profile
    directory.mkdir(parents=True, exist_ok=True)
    baseline = Path(manifest['variants']['baseline']['path'])
    combined = directory / 'combined-source.ndjson'
    initial = directory / 'producer-baseline.ndjson'
    init = directory / 'producer-init.json'
    roots = manifest.get('roots')
    if roots is None:
        from producer_delta import ROOTS
        roots = ROOTS
    write(init, dict(source_files=lean_sources(sources_at(workloads / 'baseline' / 'source')),
                     profile=manifest.get('profile', 'original-v1'), roots=roots,
                     baseline_export=str(initial)))
    lean = Path(manifest['tools']['lean']['path'])
    environment = dict(os.environ, LEAN_SYSROOT=str(lean.parent.parent), LEAN_PATH='',
                       PATH=str(lean.parent) + os.pathsep + os.environ.get('PATH', ''))
    producer = JsonProcess([args.producer, init], directory / 'producer.stderr', env=environment)
    try:
        ready = producer.receive()
        require(ready.get('status') == 'ready' and file_hash(initial) == file_hash(baseline),
                'independent full-source producer baseline differs from pin')
        initial.unlink()
        request = dict(op='fresh', source_files=lean_sources(plan[1]['sources']), export_path=str(combined))
        write(directory / 'combined-source-request.json', request)
        response = producer.request(request)
        require(response.get('status') == 'fresh', 'independent combined-source export failed')
        write(directory / 'combined-source-response.json', response)
    finally:
        producer.close()
    exports = {0: baseline, 1: Path(manifest['variants']['early-definition']['path']),
               2: combined, 3: Path(manifest['variants']['unrelated-definition']['path'])}
    indices, records = {}, {}
    for state, export in exports.items():
        folder = directory / str(state)
        native, process = fresh_index(export, args.indexer, folder / 'native')
        python, pyprocess = fresh_index(export, args.indexer, folder / 'python', python=True)
        require(canonical(native) == canonical(python), 'independent source-state Python/native full indexes disagree')
        indices[state] = native
        records[str(state)] = dict(source_state=state, export_sha256=file_hash(export),
                                   export_bytes=export.stat().st_size, index_sha256=digest(native),
                                   native_process=process, python_process=pyprocess,
                                   python_native_exact=True,
                                   compressed_files=compact_directory(folder, args.out))
    records['2']['source_export_witness'] = archive_blob(combined, args.out)
    combined.unlink()
    write(directory / 'manifest.json', records)
    return indices, records


def new_session(args, root, workloads):
    from revision_chain import RevisionChainSession
    return RevisionChainSession(root=root, workloads=workloads, producer=args.producer,
                                checker=args.checker, indexer=args.indexer,
                                index_session=args.index_session, authority_key=args.authority_key,
                                retained_checker=args.retained_checker)


def sequence_sample(args, profile, workloads, repetition, plan, refs, seen_exports, progress):
    directory = args.out / 'profiles' / profile / ('pair-' + str(repetition))
    directory.mkdir(parents=True, exist_ok=True)
    pair = dict(repetition=repetition, completed=False, correctness_passed=False,
                accepted_revisions=0, steps=[],
                order='Each production apply, then fresh full Rust on its identical sealed input before index oracles.',
                timing_scope='Paired API component sums; observed elapsed additionally includes interleaved independent oracles.')
    progress(pair)
    observed_start = setup_start = time.perf_counter()
    setup_cpu_start = adapter_cpu_time()
    session = None
    closed = False
    try:
        session = new_session(args, directory / 'session', workloads)
        constructor = time.perf_counter() - setup_start
        tick = time.perf_counter()
        ready = session.start()
        start_wall = time.perf_counter() - tick
        setup_wall = time.perf_counter() - setup_start
        setup_cpu = session.cpu_time() - setup_cpu_start
        require(session.baseline_result.get('status') == 'VERIFIED' and session.revision == 0 and
                hexid(session.head_id) and hexid(session.base_id), 'genesis session was not actually admitted')
        manifest = json.loads((workloads / 'manifest.json').read_bytes())
        baseline_export = Path(manifest['variants']['baseline']['path'])
        require(file_hash(baseline_export) == session.old['export_sha256'], 'genesis direct input differs from admitted source')
        genesis_direct = full_kernel(args.full_checker, baseline_export, directory / 'genesis-direct-rust')
        require(file_hash(baseline_export) == session.old['export_sha256'], 'genesis input changed during fresh checking')
        pair['setup'] = dict(constructor_wall_seconds=constructor, start_wall_seconds=start_wall,
                             wall_seconds=setup_wall, cpu_seconds=setup_cpu,
                             ready=safe(ready), baseline_result=safe(session.baseline_result))
        pair['genesis'] = dict(head_id=session.head_id, evidence_id=session.base_id,
                               export_sha256=session.old['export_sha256'],
                               baseline_export_path=str(baseline_export),
                               direct_rust=genesis_direct, index_sha256=digest(refs[0]),
                               baseline_witness=archive_blob(baseline_export, args.out))
        previous_index = refs[0]
        for number, step in enumerate(plan, 1):
            folder = directory / ('revision-%03d' % number)
            folder.mkdir(parents=True, exist_ok=True)
            parent_head, parent_evidence = session.head_id, session.base_id
            parent_source_root = session.source_root
            require(session.revision == number - 1, 'live revision skipped before source capture')
            tick, cpu_tick = time.perf_counter(), session.cpu_time()
            result = session.apply(step['source_dir'], tuple(step['patch']), step['claimed_names'])
            apply_wall = time.perf_counter() - tick
            apply_cpu = session.cpu_time() - cpu_tick
            result_path = folder / 'result.json'
            write(result_path, result)
            require(result.get('status') == 'VERIFIED', 'real revision refused: ' + str(result.get('reason', result)))
            link = validate_link(result, parent_head, parent_evidence, number)
            require(session.head_id == link['head_id'] and session.base_id == result['evidence_id'] and
                    session.revision == number and session.source_root == step['source_root'],
                    'live session did not promote the accepted source/evidence/head')
            snapshot = sealed_snapshot(session.snapshot_path)
            require(snapshot['sha256'] == result['export_sha256'], 'sealed current revision differs from actual acceptance')
            # Preserve the original comparator order: no full-index oracle has
            # just reparsed this sealed revision before the fresh Rust command.
            direct = full_kernel(args.full_checker, session.snapshot_path, folder / 'direct-rust')
            current, index_process = fresh_index(session.snapshot_path, args.indexer, folder / 'native-index')
            index_process.update(input_sha256=snapshot['sha256'], input_bytes=snapshot['bytes'])
            write(folder / 'native-index' / 'process.json', index_process)
            require(canonical(current) == canonical(refs[step['state']]),
                    'actual sealed revision differs from independent full source-state export')
            partition = audit_partition(result, previous_index, current)
            receipt = audit_chain_receipt(session.root, result, previous_index, current,
                                           args.authority_key.read_bytes(), partition, step, parent_source_root)
            runtime_audit = session.audit_current_acceptance(current)
            require(runtime_audit['issuer_hmac_valid'] is True and runtime_audit['all_content_addresses_valid'] is True,
                    'supplementary runtime head/source/receipt audit failed')
            native = result.get('native_kernel_report')
            require(type(native) is dict and native.get('status') == 'checked' and native.get('code') == 0 and
                    native.get('checked') == len(partition['checked_indices']) and
                    native.get('total_declarations') == current['count'] and
                    native.get('kernel') == 'sokonanoda_real_selected_declaration_check',
                    'retained Rust did not actually check the independently selected obligations')
            representative = {}
            if repetition == 0 and number <= 4:
                python, python_process = fresh_index(session.snapshot_path, args.indexer, folder / 'python-index', python=True)
                python_process.update(input_sha256=snapshot['sha256'], input_bytes=snapshot['bytes'])
                write(folder / 'python-index' / 'process.json', python_process)
                require(canonical(python) == canonical(current), 'representative live Python/native full indexes disagree')
                representative['python_index'] = python_process
                for name in ('leanchecker', 'leanchecker-paranoid'):
                    representative[name] = full_kernel(manifest['tools'][name]['path'], session.snapshot_path,
                                                       folder / name, cpp=True)
            export_witness = None
            if snapshot['sha256'] not in seen_exports:
                export_witness = archive_blob(session.snapshot_path, args.out)
                seen_exports.add(snapshot['sha256'])
            result_witness = archive_blob(result_path, args.out)
            result_path.unlink()
            # The independent fresh full-index stdout and pretty index are
            # large and often identical across restorations. Keep exact bytes
            # once in a content-addressed compressed store, retaining every
            # actual command, stdout digest and per-revision identity.
            archives = compact_directory(folder, args.out)
            observation = dict(revision=number, cycle=step['cycle'], state=step['state'], name=step['name'],
                               source_root=step['source_root'], status=result['status'],
                               evidence_id=result['evidence_id'], previous_evidence=result['previous_evidence'],
                               revision_chain=link, apply_wall_seconds=apply_wall, apply_cpu_seconds=apply_cpu,
                               snapshot=snapshot, direct_rust=direct, full_index_exact=True,
                               full_index_sha256=digest(current), full_index_process=index_process,
                               partition_audit=partition, receipt_audit=receipt, runtime_audit=runtime_audit,
                               representative_cpp=representative,
                               kernel_report=native, typed_update=result.get('typed_update'),
                               phases=result.get('timings'), memory=result.get('memory'),
                               result_witness=result_witness, export_witness=export_witness,
                               compressed_oracle_files=archives)
            pair['steps'].append(observation)
            pair['accepted_revisions'] = len(pair['steps'])
            previous_index = current
            progress(pair)
            print(json.dumps(dict(profile=profile, pair=repetition, revision=number,
                                  status=result['status'], checked=result['counts']['rechecked'],
                                  reused=result['counts']['reused'])), flush=True)
        pair['final_head'] = session.head_id
        pair['final_evidence'] = session.base_id
        pair['final_export_sha256'] = pair['steps'][-1]['snapshot']['sha256']
        pair['final_memory'] = session.memory_observation()
        tick, close_cpu_start = time.perf_counter(), session.cpu_time()
        session.close()
        close_wall = time.perf_counter() - tick
        close_cpu = session.cpu_time() - close_cpu_start
        closed = True
        pair['observed_constructor_through_close_wall_seconds'] = time.perf_counter() - observed_start
        pair['components'] = lifecycle_components(setup_wall,
            [step['apply_wall_seconds'] for step in pair['steps']], close_wall,
            genesis_direct['wall_seconds'], [step['direct_rust']['wall_seconds'] for step in pair['steps']])
        pair['components']['close_scope'] = 'Supported adapter close terminates/waits daemons and removes private files; no Rust EOF/destructor guarantee.'
        pair['cpu_components'] = lifecycle_cpu_components(setup_cpu,
            [step['apply_cpu_seconds'] for step in pair['steps']], close_cpu,
            genesis_direct['completed_child_cpu_seconds'],
            [step['direct_rust']['completed_child_cpu_seconds'] for step in pair['steps']])
        if repetition == 0:
            cold = None
            tick = time.perf_counter()
            try:
                cold = new_session(args, directory / 'session', workloads)
                cold_ready = cold.start(expected_head=pair['final_head'])
                cold_setup = time.perf_counter() - tick
                require(cold.head_id == pair['final_head'] and cold.base_id == pair['final_evidence'] and
                        cold.revision == len(plan) and canonical(cold.old['index']) == canonical(previous_index),
                        'cold expected-head replay changed current evidence, revision, or full index')
                cold_snapshot = sealed_snapshot(cold.snapshot_path)
                require(cold_snapshot['sha256'] == pair['final_export_sha256'], 'cold replay changed exact export bytes')
                pair['cold_replay'] = dict(passed=True, expected_head=pair['final_head'],
                                           actual_head=cold.head_id, replayed_revisions=cold.revision,
                                           setup_wall_seconds=cold_setup, snapshot=cold_snapshot,
                                           ready=safe(cold_ready), scope='Separate full authenticated replay, excluded from primary lifetime components.')
            finally:
                if cold is not None:
                    tick = time.perf_counter(); cold.close()
                    if 'cold_replay' in pair:
                        pair['cold_replay']['close_wall_seconds'] = time.perf_counter() - tick
        pair['compressed_session_files'] = compact_directory(directory / 'session', args.out)
        pair['completed'] = pair['correctness_passed'] = True
        progress(pair)
        return pair
    except Exception as error:
        pair['error'] = repr(error)
        progress(pair)
        raise
    finally:
        if session is not None and not closed:
            session.close()


def compact_continuous_result(result, expected, source_root):
    partition = expected['partition_audit']
    selected = len(partition['checked_indices'])
    counts = dict(total=partition['actual_kernel_total'], scheduled=selected,
                  rechecked=partition['actual_kernel_checked'],
                  reused=partition['independently_replayed_reused'], invalidated=selected)
    native = result.get('native_kernel_report', {})
    require(result.get('status') == 'VERIFIED' and result.get('export_sha256') == expected['snapshot']['sha256'] and
            result.get('representation', {}).get('export_bytes') == expected['snapshot']['bytes'] and
            source_root == expected['source_root'] and canonical(result.get('counts')) == canonical(counts) and
            native.get('status') == 'checked' and native.get('code') == 0 and
            native.get('checked') == counts['rechecked'] and native.get('total_declarations') == counts['total'],
            'uninterrupted actual revision differs from independently checked input/source/obligations')
    compact = {field: copy.deepcopy(result[field]) for field in (
        'status', 'evidence_id', 'previous_evidence', 'export_sha256', 'revision_chain',
        'counts', 'native_kernel_report', 'producer_provenance', 'checker_result', 'representation', 'timings')}
    compact.update(source_root=source_root, snapshot_bytes=result['representation']['export_bytes'])
    return compact


def uninterrupted_candidate(args, workloads, directory, plan, pair):
    """Only production APIs and compact result recording occur inside the timer."""
    session, closed = None, False
    observations = []
    cpu_start, wall_start = adapter_cpu_time(), time.perf_counter()
    try:
        session = new_session(args, directory / 'session', workloads)
        ready = session.start()
        require(session.baseline_result.get('status') == 'VERIFIED' and session.revision == 0 and
                session.old['export_sha256'] == pair['genesis']['export_sha256'],
                'uninterrupted genesis differs from independently checked baseline')
        genesis = dict(head_id=session.head_id, evidence_id=session.base_id,
                       export_sha256=session.old['export_sha256'], revision=0,
                       source_root=session.source_root, ready=ready)
        for revision, (step, expected) in enumerate(zip(plan, pair['steps']), 1):
            parent_head, parent_evidence = session.head_id, session.base_id
            result = session.apply(step['source_dir'], tuple(step['patch']), step['claimed_names'])
            validate_link(result, parent_head, parent_evidence, revision)
            observations.append(compact_continuous_result(result, expected, session.source_root))
            # Drop the complete decisions before advancing; the timed arm
            # retains only the compact observation returned above.
            result = None
        final_head, final_evidence = session.head_id, session.base_id
        session.close()
        closed = True
        wall_seconds, cpu_seconds = time.perf_counter() - wall_start, session.cpu_time() - cpu_start
        return dict(completed=True, wall_seconds=wall_seconds, cpu_seconds=cpu_seconds,
                    genesis=genesis, steps=observations, final_head=final_head, final_evidence=final_evidence,
                    scope='Uninterrupted constructor/start, all production applies with compact input/count recording, '
                          'and supported close. No independent oracle, hashing, compression, or evidence writes between APIs.',
                    cpu_scope='Adapter + completed child CPU plus live-daemon ticks; SC_CLK_TCK granularity.')
    finally:
        if session is not None and not closed:
            session.close()


def uninterrupted_direct(args, directory, expected_inputs, prepared):
    commands, outputs = [], []
    cpu_start, wall_start = adapter_cpu_time(), time.perf_counter()
    for revision, identity in enumerate(expected_inputs):
        item = prepared[identity]
        command = [str(args.full_checker), str(item['config'])]
        child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
        tick = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True, timeout=180)
            code, stdout, stderr, timed_out = result.returncode, result.stdout, result.stderr, False
        except subprocess.TimeoutExpired as error:
            code, stdout, stderr, timed_out = None, error.stdout or b'', error.stderr or b'', True
        wall = time.perf_counter() - tick
        child_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        require(code == 0 and not timed_out, 'uninterrupted direct full Rust command rejected or failed')
        commands.append(dict(revision=revision, command=command, returncode=code, timed_out=timed_out,
                             wall_seconds=wall,
                             completed_child_cpu_seconds=child_end.ru_utime + child_end.ru_stime - child_start.ru_utime - child_start.ru_stime,
                             snapshot=item['snapshot'], input_sha256=identity, input_bytes=item['snapshot']['bytes'],
                             config_path=str(item['config']), config_sha256=item['config_sha256']))
        outputs.append((stdout, stderr))
    wall_seconds, cpu_seconds = time.perf_counter() - wall_start, adapter_cpu_time() - cpu_start
    return dict(completed=True, wall_seconds=wall_seconds, cpu_seconds=cpu_seconds, commands=commands,
                scope='Uninterrupted fresh full Rust commands at genesis and every identical accepted revision; '
                      'process creation, output capture, exit and compact recording included. Input decompression/sealing and config preparation are outside timing.'), outputs


def continuous_sample(args, profile, workloads, repetition, plan, refs, pair, all_pairs):
    directory = args.out / 'profiles' / profile / ('pair-' + str(repetition)) / 'continuous'
    directory.mkdir(parents=True, exist_ok=True)
    witnesses = {}
    for previous in all_pairs:
        baseline = previous['genesis']['baseline_witness']
        witnesses[baseline['uncompressed_sha256']] = baseline
        for step in previous['steps']:
            if step.get('export_witness'):
                blob = step['export_witness']; witnesses[blob['uncompressed_sha256']] = blob
    expected_inputs = [pair['genesis']['export_sha256']] + [step['snapshot']['sha256'] for step in pair['steps']]
    prepared, descriptors = {}, []
    try:
        # The exact inputs were already independently indexed/full-checked by
        # the interleaved arm. Prepare sealed read-only copies before timing
        # either continuous arm, so their order can alternate honestly.
        for identity in dict.fromkeys(expected_inputs):
            blob = witnesses[identity]
            require(file_hash(blob['path']) == blob['sha256'], 'continuous input compressed witness changed')
            descriptor = os.memfd_create('revision-chain-direct', getattr(os, 'MFD_ALLOW_SEALING', 2))
            descriptors.append(descriptor)
            with gzip.open(blob['path'], 'rb') as source:
                while chunk := source.read(1 << 20):
                    view = memoryview(chunk)
                    while view:
                        written = os.write(descriptor, view); view = view[written:]
            fcntl.fcntl(descriptor, getattr(fcntl, 'F_ADD_SEALS', 1033), 15)
            path = Path('/proc') / str(os.getpid()) / 'fd' / str(descriptor)
            snapshot = sealed_snapshot(path)
            require(snapshot['sha256'] == identity and snapshot['bytes'] == blob['uncompressed_bytes'],
                    'continuous direct input differs from exact independently checked witness')
            config = directory / 'direct' / 'configs' / (identity + '.json')
            write(config, configuration(path))
            prepared[identity] = dict(snapshot=snapshot, config=config, config_sha256=file_hash(config))
        order = ['candidate', 'direct'] if repetition % 2 == 0 else ['direct', 'candidate']
        observation = dict(completed=False, order=order)
        outputs = None
        for arm in order:
            if arm == 'candidate':
                observation[arm] = uninterrupted_candidate(args, workloads, directory / 'candidate', plan, pair)
            else:
                observation[arm], outputs = uninterrupted_direct(args, directory / 'direct', expected_inputs, prepared)
        # Everything below is after both uninterrupted outer intervals.
        candidate = observation['candidate']
        previous_index, previous_source_root = refs[0], candidate['genesis']['source_root']
        for step, actual, expected in zip(plan, candidate['steps'], pair['steps']):
            actual['receipt_audit'] = audit_chain_receipt(directory / 'candidate' / 'session', actual,
                previous_index, refs[step['state']], args.authority_key.read_bytes(), expected['partition_audit'], step, previous_source_root)
            actual['full_index_exact'] = True
            actual['independent_full_index_sha256'] = expected['full_index_sha256']
            previous_index, previous_source_root = refs[step['state']], step['source_root']
        for record, (stdout, stderr) in zip(observation['direct']['commands'], outputs):
            folder = directory / 'direct' / ('revision-%03d' % record['revision'])
            folder.mkdir(parents=True, exist_ok=True)
            for kind, raw in (('stdout', stdout), ('stderr', stderr)):
                path = folder / ('process.' + kind); path.write_bytes(raw)
                record[kind + '_path'] = str(path); record[kind + '_sha256'] = hashlib.sha256(raw).hexdigest()
            write(folder / 'process.json', record)
        candidate['compressed_session_files'] = compact_directory(directory / 'candidate' / 'session', args.out)
        observation['completed'] = True
        write(directory / 'summary.json', observation)
        observation['summary_path'] = str(directory / 'summary.json')
        observation['summary_sha256'] = file_hash(directory / 'summary.json')
        return observation
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def source_manifest():
    paths = ['Cargo.toml', 'Cargo.lock', '.github/workflows/incremental-revision-chain.yml']
    paths += [str(path.relative_to(REPO)) for path in (REPO / 'src').rglob('*.rs')]
    paths += [str(path.relative_to(REPO)) for path in HERE.glob('*.py')]
    paths += [str(path.relative_to(REPO)) for path in HERE.glob('*.lean')]
    paths += [str(path.relative_to(REPO)) for path in HERE.glob('*.json')]
    return {path: file_hash(REPO / path) for path in sorted(set(paths)) if (REPO / path).is_file()}


def write_summary(args, report):
    write(args.out / 'summary.json', report)
    phases = copy.deepcopy(report)
    for profile in phases.get('profiles', {}).values():
        for pair in profile['pairs']:
            for step in pair['steps']:
                # Complete selected indexes stay in the primary evidence report.
                audit = step.get('partition_audit', {})
                for name in ('checked_indices', 'reused_indices'):
                    if name in audit:
                        audit[name + '_sha256'] = digest(audit.pop(name))
    write(args.out / 'compact-phases.json', phases)


def run(args):
    require(not args.out.exists() or not any(args.out.iterdir()), 'use a fresh evidence output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    require(args.authority_key.is_file() and len(args.authority_key.read_bytes()) == 32,
            'issuer authority must be an existing 32-byte key outside evidence')
    require(args.out != args.authority_key and args.out not in args.authority_key.parents,
            'issuer authority must remain outside published evidence')
    status = subprocess.check_output(['git', 'status', '--porcelain', '--', 'src',
        'experiments/incremental', '.github/workflows/incremental-revision-chain.yml'], cwd=REPO, text=True)
    report = dict(schema=SCHEMA, source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                  source_tracked_clean=not bool(status.strip()), source_git_status=status,
                  source_sha256=source_manifest(), binary_sha256={}, repetitions=args.repetitions,
                  cycles=args.cycles, requested_profiles=args.profiles, completed=False,
                  correctness_passed=False, qualified=False, profiles={},
                  host=dict(uname=list(platform.uname()), cpu_model=next((line.split(':', 1)[1].strip()
                    for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), None)),
                  measurement_policy=dict(
                    primary='Sum of measured constructor/start, all accepted apply APIs, supported shutdown. No projected amortization.',
                    continuous_primary='Uninterrupted constructor/start through all accepted applies and supported close; no intervening independent oracles or evidence packaging.',
                    continuous_direct='Uninterrupted fresh full Rust commands at genesis and every identical accepted revision; exact input preparation is outside timing.',
                    direct='Sum of actual fresh full Rust command wall durations at genesis and every exact sealed revision; process creation and exit included.',
                    order='Production apply then same-input direct Rust, before full-index oracle; fixed within-revision order explicitly retained.',
                    observed='Constructor-through-close elapsed includes interleaved oracles and harness evidence packaging; never presented as uninterrupted production lifecycle.',
                    cold='One final expected-head full cold replay per profile; measured separately from all primary paired lifetime sums.',
                    memory='Raw post-phase procfs RSS/cumulative VmHWM; missing processes are not zero, no total peak claim.'),
                  limits=['Frozen original/expanded Lean 4.35 source universe and same-kind declaration schedule.',
                          'Unproved source/export/parser/identity executable bridge remains trusted.',
                          'Full index/reference/oracle work and complete export materialization remain linear.',
                          'Paired observed API component economics are same-host, with warm OS caches and fixed direct-after-update order.'])
    for name in ('producer', 'checker', 'retained_checker', 'indexer', 'index_session', 'full_checker'):
        path = getattr(args, name)
        report['binary_sha256'][name] = dict(path=str(path), sha256=file_hash(path))
    write_summary(args, report)
    try:
        for profile in args.profiles:
            workloads = getattr(args, profile + '_workloads')
            plan = source_directories(args, profile, workloads)
            refs, reference_records = references(args, profile, workloads, plan)
            report['profiles'][profile] = dict(pairs=[], references=reference_records)
            for name, info in json.loads((workloads / 'manifest.json').read_bytes())['tools'].items():
                if name in ('lean', 'leanchecker', 'leanchecker-paranoid'):
                    report['binary_sha256'][profile + ':' + name] = dict(path=info['path'], sha256=file_hash(info['path']))
            seen_exports = set()
            for repetition in range(args.repetitions):
                def progress(pair):
                    pairs = report['profiles'][profile]['pairs']
                    if len(pairs) == repetition:
                        pairs.append(pair)
                    else:
                        pairs[repetition] = pair
                    write_summary(args, report)
                pair = sequence_sample(args, profile, workloads, repetition, plan, refs, seen_exports, progress)
                pair['continuous'] = continuous_sample(args, profile, workloads, repetition, plan, refs, pair,
                                                       report['profiles'][profile]['pairs'])
                progress(pair)
            pairs = report['profiles'][profile]['pairs']
            economics = paired_economics([dict(
                apply_wall_seconds=pair['components']['api_component_sum_wall_seconds'],
                direct_wall_seconds=pair['components']['direct_full_rust_component_sum_wall_seconds']) for pair in pairs], seed=20261022)
            economics.update(scope=report['measurement_policy']['primary'], comparator=report['measurement_policy']['direct'],
                             setup_in_timed_update=True,
                             accepted_revisions_per_pair=len(plan), paired_sequences=len(pairs),
                             claim_status='QUALIFICATION_REQUIRES_FIVE_EXACT_PAIRED_LIFETIMES' if len(pairs) < 5 else 'OBSERVED_COMPONENT_SUMS')
            report['profiles'][profile]['economics'] = economics
            cpu_economics = paired_economics([dict(
                apply_wall_seconds=pair['cpu_components']['api_component_sum_cpu_seconds'],
                direct_wall_seconds=pair['cpu_components']['direct_full_rust_component_sum_cpu_seconds']) for pair in pairs], seed=20261023)
            cpu_economics.update(scope=pairs[0]['cpu_components']['scope'], measurement='cpu_seconds', setup_in_timed_update=True)
            report['profiles'][profile]['cpu_economics'] = cpu_economics
            for name, field, seed in (('continuous_economics', 'wall_seconds', 20261024),
                                      ('continuous_cpu_economics', 'cpu_seconds', 20261025)):
                measured = paired_economics([dict(apply_wall_seconds=p['continuous']['candidate'][field],
                    direct_wall_seconds=p['continuous']['direct'][field]) for p in pairs], seed=seed)
                measured.update(scope=report['measurement_policy']['continuous_primary'],
                                comparator=report['measurement_policy']['continuous_direct'],
                                measurement=field, setup_in_timed_update=True,
                                accepted_revisions_per_pair=len(plan), paired_sequences=len(pairs))
                if len(pairs) < 5:
                    measured.update(observed_status=measured['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
                report['profiles'][profile][name] = measured
            if len(pairs) < 5:
                for observed in (economics, cpu_economics):
                    observed.update(observed_status=observed['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
            for revision in range(len(plan)):
                per_step = paired_economics([dict(apply_wall_seconds=p['steps'][revision]['apply_wall_seconds'],
                    direct_wall_seconds=p['steps'][revision]['direct_rust']['wall_seconds']) for p in pairs], seed=20261022 + revision)
                if len(pairs) < 5:
                    per_step.update(observed_status=per_step['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
                report['profiles'][profile].setdefault('revision_economics', []).append(dict(revision=revision + 1, economics=per_step))
            del refs
        for path, expected in report['source_sha256'].items():
            require(file_hash(REPO / path) == expected, 'measured source drift: ' + path)
        for name, record in report['binary_sha256'].items():
            require(file_hash(record['path']) == record['sha256'], 'measured executable drift: ' + name)
        report['source_and_binary_stable'] = True
        report['completed'] = report['correctness_passed'] = True
        report['qualified'] = (not args.smoke and args.repetitions == 5 and args.cycles == 10 and
                               set(args.profiles) == {'original', 'expanded'} and report['source_tracked_clean'])
        report['qualification_status'] = 'QUALIFIED_BOUNDED' if report['qualified'] else 'SMOKE_CORRECTNESS_ONLY'
        write_summary(args, report)
        lines = ['# Authenticated continuing-revision observations', '',
                 'Primary metric is the uninterrupted constructor/start → every accepted revision → supported shutdown wall interval. '
                 'A separate direct arm runs fresh Rust on genesis and every identical accepted revision; arm order alternates. '
                 'Independent full-index/kernel/receipt audits run outside these intervals. '
                 'The interleaved arm separately retains observed API component sums and complete oracle-inclusive elapsed.', '',
                 '| Profile | Pairs | Revisions per pair | Uninterrupted candidate median, s | Uninterrupted fresh Rust median, s | Status |',
                 '| --- | ---: | ---: | ---: | ---: | --- |']
        for profile, value in report['profiles'].items():
            economics = value['continuous_economics']
            lines.append(f"| {profile} | {len(value['pairs'])} | {4 * args.cycles} | "
                         f"{economics['apply_median_wall_seconds']:.6f} | {economics['direct_median_wall_seconds']:.6f} | {economics['status']} |")
        lines += ['', 'Qualification: ' + report['qualification_status'] + '. '
                  'NO_SPEEDUP is retained as a measured economic outcome, independently of correctness.']
        (args.out / 'summary.md').write_text('\n'.join(lines) + '\n')
        print(json.dumps(dict(completed=True, qualified=report['qualified'],
                              qualification_status=report['qualification_status'],
                              summary_sha256=file_hash(args.out / 'summary.json'))), flush=True)
        return report
    except Exception as error:
        report['error'] = repr(error)
        write_summary(args, report)
        raise


def verify_summary(path, expected_source, *, allow_smoke=False):
    """Strict read-only report review, including raw results and full-index replay.

    The historical issuer key stays private. This reader checks signed object
    addresses and observed issuer-audit witnesses; it does not claim to
    reauthenticate historical HMACs without that key.
    """
    path = Path(path).resolve()
    out = path.parent
    report = json.loads(path.read_bytes(), object_pairs_hook=strict_object)
    require(report.get('schema') == SCHEMA and report.get('source_sha') == expected_source and
            all(report.get(flag) is True for flag in ('completed', 'correctness_passed', 'source_and_binary_stable')),
            'report has incomplete/failed correctness or source stability')
    require(allow_smoke or (report.get('source_tracked_clean') is True and report.get('qualified') is True and
            report.get('repetitions') == 5 and report.get('cycles') == 10 and
            set(report.get('profiles', {})) == {'original', 'expanded'}),
            'report is not an exact-source complete five-pair forty-revision qualification')
    require(type(report.get('repetitions')) is int and report['repetitions'] > 0 and
            type(report.get('cycles')) is int and report['cycles'] > 0,
            'positive actual sequence counts are required even for smoke evidence')
    requested = report.get('requested_profiles')
    require(type(requested) is list and bool(requested) and len(set(requested)) == len(requested) and
            set(requested) <= {'original', 'expanded'} and set(report.get('profiles', {})) == set(requested),
            'nonempty unique supported requested profiles must match actual profile reports')
    require(type(report.get('source_sha256')) is dict and
            set(report['source_sha256']) == set(source_manifest()), 'measured source manifest is incomplete or foreign')
    expected_tools = {'producer', 'checker', 'retained_checker', 'indexer', 'index_session', 'full_checker'}
    expected_tools |= {profile + ':' + name for profile in requested
                       for name in ('lean', 'leanchecker', 'leanchecker-paranoid')}
    require(type(report.get('binary_sha256')) is dict and set(report['binary_sha256']) == expected_tools,
            'measured binary manifest is incomplete or foreign')
    expected_pairs, expected_revisions = report['repetitions'], 4 * report['cycles']
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == expected_source,
            'summary reviewer is running against a different source revision')
    for source, identity in report['source_sha256'].items():
        require(file_hash(REPO / source) == identity, 'summary source changed: ' + source)
    for name, record in report['binary_sha256'].items():
        require(file_hash(record['path']) == record['sha256'], 'summary executable changed: ' + name)
    checked_archives = {}
    index_cache = {}
    arithmetic_checks = 0
    def archive_path(record):
        target = Path(record['path'])
        if not target.is_file():
            target = out / record['artifact_relative_path']
        require(target.resolve().is_relative_to(out) and target.is_file(), 'evidence archive is outside report directory or missing')
        return target
    def archive_check(record):
        target = archive_path(record)
        descriptor = archive_descriptor(record, checked_archives.get(str(target)))
        if str(target) not in checked_archives:
            require(file_hash(target) == record['sha256'] and target.stat().st_size == record['bytes'],
                    'compressed exact-byte witness changed')
            identity, length = hashlib.sha256(), 0
            with gzip.open(target, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b''):
                    identity.update(chunk); length += len(chunk)
            require(identity.hexdigest() == record['uncompressed_sha256'] and length == record['uncompressed_bytes'],
                    'uncompressed exact-byte witness changed')
            checked_archives[str(target)] = descriptor
        return target
    def archive_json(record):
        with gzip.open(archive_check(record), 'rb') as stream:
            return json.load(stream, object_pairs_hook=strict_object)
    def saved(path):
        path = Path(path)
        if path.is_file():
            return path.read_bytes()
        record = json.loads(path.with_name(path.name + '.archive.json').read_bytes(), object_pairs_hook=strict_object)
        with gzip.open(archive_check(record), 'rb') as stream:
            return stream.read()
    def index_from_process(process):
        require(process.get('returncode') == 0 and process.get('timed_out') is False,
                'full-index process failed or timed out')
        identity = process['stdout_sha256']
        if identity not in index_cache:
            raw = saved(process['stdout_path'])
            require(hashlib.sha256(raw).hexdigest() == identity, 'actual full-index stdout bytes changed')
            index_cache[identity] = json.loads(raw, object_pairs_hook=strict_object)
        return index_cache[identity]
    def command_ok(process, snapshot, binary):
        require(process.get('returncode') == 0 and process.get('timed_out') is False and
                process.get('input_sha256') == snapshot['sha256'] and
                process.get('input_bytes') == snapshot['bytes'] and
                Path(process['command'][0]).resolve() == Path(binary).resolve(),
                'actual full-kernel command, input identity, or outcome disagrees')
        require(type(process['wall_seconds']) in (float, int) and math.isfinite(process['wall_seconds']) and
                process['wall_seconds'] > 0, 'invalid actual full-kernel duration')
        raw_config = saved(process['config_path'])
        require(hashlib.sha256(raw_config).hexdigest() == process['config_sha256'] and
                canonical(json.loads(raw_config, object_pairs_hook=strict_object)) == canonical(configuration(snapshot['path'])),
                'actual full-kernel config differs from the hashed snapshot input')
        expected_command = ([binary, '--from-export', snapshot['path']] if '--from-export' in process['command']
                            else [binary, process['config_path']])
        require(process['command'] == [str(part) for part in expected_command],
                'actual kernel invocation does not read the declared identical snapshot')
        for kind in ('stdout', 'stderr'):
            raw = saved(process[kind + '_path'])
            require(hashlib.sha256(raw).hexdigest() == process[kind + '_sha256'],
                    'actual kernel output bytes changed')
    full_binary = report['binary_sha256']['full_checker']['path']
    for profile, profile_report in report['profiles'].items():
        pairs = profile_report['pairs']
        actual_inputs, witnessed_inputs = set(), set()
        require(len(pairs) == expected_pairs, 'missing complete lifetime pairs: ' + profile)
        references_by_state = {int(state): index_from_process(record['native_process'])
                               for state, record in profile_report['references'].items()}
        for state, record in profile_report['references'].items():
            require(record['python_native_exact'] is True and digest(references_by_state[int(state)]) == record['index_sha256'],
                    'independent source-state reference changed')
            require(canonical(index_from_process(record['python_process'])) == canonical(references_by_state[int(state)]),
                    'source-state native/Python index differential failed')
            for blob in record['compressed_files']:
                archive_check(blob)
            if 'source_export_witness' in record:
                archive_check(record['source_export_witness'])
        for number, pair in enumerate(pairs):
            require(pair['completed'] is True and pair['correctness_passed'] is True and
                    pair['repetition'] == number and pair['accepted_revisions'] == expected_revisions and len(pair['steps']) == expected_revisions,
                    'incomplete actual forty-revision lifetime')
            genesis = pair['genesis']
            archive_check(genesis['baseline_witness'])
            witnessed_inputs.add((genesis['baseline_witness']['uncompressed_sha256'],
                                  genesis['baseline_witness']['uncompressed_bytes']))
            actual_inputs.add((genesis['export_sha256'], genesis['baseline_witness']['uncompressed_bytes']))
            command_ok(genesis['direct_rust'], dict(sha256=genesis['export_sha256'],
                bytes=genesis['baseline_witness']['uncompressed_bytes'], path=genesis['baseline_export_path']), full_binary)
            previous_index = references_by_state[0]
            parent_head, parent_evidence = genesis['head_id'], genesis['evidence_id']
            parent_sources = sources_at(out / 'sources' / profile / '0')
            planned = revision_plan(parent_sources, report['cycles'])
            session_cache = out / 'profiles' / profile / ('pair-' + str(number)) / 'session' / 'cache'
            def object_bytes(category, identity, suffix):
                require(hexid(identity), 'invalid archived chain object identity')
                raw = saved(session_cache / category / (identity + suffix))
                require(hashlib.sha256(raw).hexdigest() == identity, 'archived chain object content address changed: ' + category)
                return raw
            def object_payload(category, identity, schema):
                envelope = json.loads(object_bytes(category, identity, '.json'), object_pairs_hook=strict_object)
                require(set(envelope) == {'payload', 'hmac_sha256'} and hexid(envelope['hmac_sha256']) and
                        envelope['payload']['schema'] == schema, 'archived signed object domain changed')
                return envelope['payload']
            for revision, step in enumerate(pair['steps'], 1):
                require(step['revision'] == revision and step['state'] == [1, 2, 3, 0][(revision - 1) % 4] and
                        step['cycle'] == (revision - 1) // 4 and step['status'] == 'VERIFIED' and
                        step['full_index_exact'] is True, 'missing/misordered actual source revision')
                result = archive_json(step['result_witness'])
                link = validate_link(result, parent_head, parent_evidence, revision)
                require(canonical(link) == canonical(step['revision_chain']) and
                        result['evidence_id'] == step['evidence_id'] and result['previous_evidence'] == step['previous_evidence'] and
                        result['export_sha256'] == step['snapshot']['sha256'],
                        'raw issued result differs from published revision witness')
                snapshot = step['snapshot']
                actual_inputs.add((snapshot['sha256'], snapshot['bytes']))
                require(type(snapshot['seals']) is int and snapshot['seals'] & 15 == 15,
                        'actual accepted revision was not fully sealed')
                command_ok(step['direct_rust'], snapshot, full_binary)
                current = index_from_process(step['full_index_process'])
                require(step['full_index_process']['input_sha256'] == snapshot['sha256'] and
                        canonical(current) == canonical(references_by_state[step['state']]) and
                        digest(current) == step['full_index_sha256'],
                        'actual full-index oracle differs from exact source-state reference')
                index_command = step['full_index_process']['command']
                require(index_command[0] == report['binary_sha256']['indexer']['path'] and len(index_command) == 2 and
                        canonical(json.loads(saved(index_command[1]), object_pairs_hook=strict_object)) == canonical(configuration(snapshot['path'])),
                        'actual full-index invocation reads a different snapshot')
                partition = audit_partition(result, previous_index, current)
                require(canonical(partition) == canonical(step['partition_audit']), 'independent selected-set replay changed')
                audit = step['receipt_audit']
                require(audit['issuer_hmac_valid'] is True and audit['all_content_addresses_valid'] is True and
                        audit['full_index_and_partition_exact'] is True and audit['receipt_schema'] == SPARSE_ACCEPTANCE and
                        audit['head_hmac_valid'] is True and audit['complete_source_capture_exact'] is True and
                        audit['previous_evidence'] == parent_evidence and audit['receipt_sha256'] == result['evidence_id'],
                        'missing actual issuer/content/full-index audit witness')
                raw_receipt = object_bytes('records', result['evidence_id'], '.json')
                envelope = json.loads(raw_receipt, object_pairs_hook=strict_object)
                payload = envelope['payload']
                require(hexid(envelope['hmac_sha256']) and payload['schema'] == SPARSE_ACCEPTANCE and
                        payload['status'] == 'VERIFIED' and payload['export_sha256'] == snapshot['sha256'] and
                        payload['previous_evidence'] == parent_evidence and
                        payload['checked_indices'] == partition['checked_indices'] and
                        canonical(reconstruct_index_patch(previous_index, payload['index_patch'])) == canonical(current),
                        'actual sparse receipt, immediate parent, selected set, or reconstruction changed')
                representation = json.loads(object_bytes('representations', payload['delta_representation'], '.json'), object_pairs_hook=strict_object)
                transition = object_payload('transitions', representation['transition_id'], 'mathgraph.lean-source-owned-transition.v1')
                delta = object_bytes('deltas', representation['delta_sha256'], '.ndjson')
                head = object_payload('chain', link['head_id'], 'mathgraph.lean-accepted-predecessor-chain.v1')
                capture = json.loads(object_bytes('source-captures', link['source_capture_id'], '.json'), object_pairs_hook=strict_object)
                expected_step = planned[revision - 1]
                require(capture['schema'] == 'mathgraph.lean-complete-source-capture.v1' and
                        canonical(capture['sources']) == canonical(expected_step['sources']) and
                        canonical(capture['patch']) == canonical(expected_step['patch']) and
                        capture['claimed_names'] == expected_step['claimed_names'] and
                        digest(capture['sources']) == step['source_root'] and
                        head['source_root'] == step['source_root'] and head['source_capture_id'] == link['source_capture_id'] and
                        head['evidence_id'] == result['evidence_id'] and head['previous_head'] == parent_head and
                        head['previous_evidence'] == parent_evidence and head['revision'] == revision and
                        head['policy_sha256'] == digest(result['producer_provenance']) and
                        head['export_sha256'] == snapshot['sha256'] and head['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
                        representation['schema'] == 'mathgraph.lean-delta-representation.v1' and
                        representation['export_sha256'] == snapshot['sha256'] and representation['base_evidence_id'] == parent_evidence and
                        transition['source_root'] == step['source_root'] and transition['baseline_source_root'] == digest(parent_sources) and
                        transition['base_evidence_id'] == parent_evidence and transition['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
                        canonical(transition['provenance']) == canonical(result['producer_provenance']),
                        'archived chain head/source capture/representation/transition/delta linkage changed')
                if number == 0 and revision <= 4:
                    controls = step['representative_cpp']
                    for tool in ('leanchecker', 'leanchecker-paranoid'):
                        command_ok(controls[tool], snapshot, report['binary_sha256'][profile + ':' + tool]['path'])
                    require(canonical(index_from_process(controls['python_index'])) == canonical(current),
                            'representative actual source-state Python/native index failed')
                if step.get('export_witness'):
                    archive_check(step['export_witness'])
                    require(step['export_witness']['uncompressed_sha256'] == snapshot['sha256'] and
                            step['export_witness']['uncompressed_bytes'] == snapshot['bytes'], 'exact complete-export witness changed')
                    witnessed_inputs.add((step['export_witness']['uncompressed_sha256'], step['export_witness']['uncompressed_bytes']))
                for blob in step['compressed_oracle_files']:
                    archive_check(blob)
                previous_index = current
                parent_sources = capture['sources']
                parent_head, parent_evidence = link['head_id'], result['evidence_id']
            require(pair['final_head'] == parent_head and pair['final_evidence'] == parent_evidence,
                    'final published head differs from actual chain')
            components = lifecycle_components(pair['setup']['wall_seconds'],
                [step['apply_wall_seconds'] for step in pair['steps']], pair['components']['close_wall_seconds'],
                genesis['direct_rust']['wall_seconds'], [step['direct_rust']['wall_seconds'] for step in pair['steps']])
            for key, value in components.items():
                require(pair['components'].get(key) == value, 'published component sum differs from observed durations: ' + key)
            cpu_components = lifecycle_cpu_components(pair['setup']['cpu_seconds'],
                [step['apply_cpu_seconds'] for step in pair['steps']], pair['cpu_components']['close_cpu_seconds'],
                genesis['direct_rust']['completed_child_cpu_seconds'],
                [step['direct_rust']['completed_child_cpu_seconds'] for step in pair['steps']])
            require(canonical(cpu_components) == canonical(pair['cpu_components']), 'published lifetime CPU component sum changed')
            require(pair['observed_constructor_through_close_wall_seconds'] >=
                    components['api_component_sum_wall_seconds'] + components['direct_full_rust_component_sum_wall_seconds'],
                    'observed elapsed improperly excludes interleaved actual oracles')
            if number == 0:
                cold = pair['cold_replay']
                require(cold['passed'] is True and cold['expected_head'] == parent_head and cold['actual_head'] == parent_head and
                        cold['replayed_revisions'] == expected_revisions and cold['snapshot']['sha256'] == pair['final_export_sha256'],
                        'missing final expected-head genuine cold replay')
            for blob in pair['compressed_session_files']:
                archive_check(blob)
            continuous = pair['continuous']
            require(continuous['completed'] is True and continuous['order'] ==
                    (['candidate', 'direct'] if number % 2 == 0 else ['direct', 'candidate']),
                    'missing or nonalternating uninterrupted lifetime pair')
            raw_continuous = saved(continuous['summary_path'])
            require(hashlib.sha256(raw_continuous).hexdigest() == continuous['summary_sha256'] and
                    canonical(json.loads(raw_continuous, object_pairs_hook=strict_object)) ==
                    canonical({key:value for key,value in continuous.items() if key not in ('summary_path', 'summary_sha256')}),
                    'raw uninterrupted lifetime evidence differs from summary')
            candidate, direct = continuous['candidate'], continuous['direct']
            for arm in (candidate, direct):
                require(arm['completed'] is True and all(type(arm[field]) in (float, int) and
                    math.isfinite(arm[field]) and arm[field] > 0 for field in ('wall_seconds', 'cpu_seconds')),
                    'missing actual uninterrupted outer wall/CPU intervals')
            require(len(candidate['steps']) == expected_revisions and len(direct['commands']) == expected_revisions + 1 and
                    candidate['genesis']['export_sha256'] == genesis['export_sha256'],
                    'incomplete uninterrupted candidate/direct revision sequence')
            session_cache = out / 'profiles' / profile / ('pair-' + str(number)) / 'continuous' / 'candidate' / 'session' / 'cache'
            parent_head, parent_evidence = candidate['genesis']['head_id'], candidate['genesis']['evidence_id']
            previous_index = references_by_state[0]
            parent_sources = sources_at(out / 'sources' / profile / '0')
            require(candidate['genesis']['source_root'] == digest(parent_sources), 'uninterrupted genesis source differs')
            for revision, (actual, expected, source_step) in enumerate(zip(candidate['steps'], pair['steps'], planned), 1):
                compact_continuous_result(actual, expected, actual['source_root'])
                link = validate_link(actual, parent_head, parent_evidence, revision)
                current = references_by_state[expected['state']]
                partition = expected['partition_audit']
                receipt = object_payload('records', actual['evidence_id'], SPARSE_ACCEPTANCE)
                require(receipt['previous_evidence'] == parent_evidence and receipt['export_sha256'] == actual['export_sha256'] and
                        receipt['checked_indices'] == partition['checked_indices'] and
                        canonical(reconstruct_index_patch(previous_index, receipt['index_patch'])) == canonical(current),
                        'uninterrupted accepted receipt differs from independent full index/selected set')
                representation = json.loads(object_bytes('representations', receipt['delta_representation'], '.json'), object_pairs_hook=strict_object)
                transition = object_payload('transitions', representation['transition_id'], 'mathgraph.lean-source-owned-transition.v1')
                delta = object_bytes('deltas', representation['delta_sha256'], '.ndjson')
                head = object_payload('chain', link['head_id'], 'mathgraph.lean-accepted-predecessor-chain.v1')
                capture = json.loads(object_bytes('source-captures', link['source_capture_id'], '.json'), object_pairs_hook=strict_object)
                require(head['evidence_id'] == actual['evidence_id'] and head['previous_head'] == parent_head and
                        head['previous_evidence'] == parent_evidence and head['revision'] == revision and
                        head['source_capture_id'] == link['source_capture_id'] and head['source_root'] == actual['source_root'] and
                        head['export_sha256'] == actual['export_sha256'] and head['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
                        head['policy_sha256'] == digest(actual['producer_provenance']) and
                        capture['schema'] == 'mathgraph.lean-complete-source-capture.v1' and
                        canonical(capture['sources']) == canonical(source_step['sources']) and
                        canonical(capture['patch']) == canonical(source_step['patch']) and capture['claimed_names'] == source_step['claimed_names'] and
                        representation['schema'] == 'mathgraph.lean-delta-representation.v1' and
                        representation['base_evidence_id'] == parent_evidence and representation['export_sha256'] == actual['export_sha256'] and
                        transition['base_evidence_id'] == parent_evidence and transition['baseline_source_root'] == digest(parent_sources) and
                        transition['source_root'] == actual['source_root'] and transition['delta_sha256'] == hashlib.sha256(delta).hexdigest() and
                        canonical(transition['provenance']) == canonical(actual['producer_provenance']) and
                        actual['receipt_audit']['issuer_hmac_valid'] is True and actual['receipt_audit']['all_content_addresses_valid'] is True and
                        actual['receipt_audit']['head_hmac_valid'] is True and actual['receipt_audit']['complete_source_capture_exact'] is True and
                        actual['full_index_exact'] is True and actual['independent_full_index_sha256'] == expected['full_index_sha256'],
                        'uninterrupted actual source/head/transition/receipt audit differs from preserved independent evidence')
                previous_index, parent_sources = current, capture['sources']
                parent_head, parent_evidence = link['head_id'], actual['evidence_id']
            require(candidate['final_head'] == parent_head and candidate['final_evidence'] == parent_evidence and
                    candidate['wall_seconds'] >= sum(step['timings']['end_to_end_seconds'] for step in candidate['steps']),
                    'uninterrupted candidate outer interval or final head is incomplete')
            expected_inputs = [(genesis['export_sha256'], genesis['baseline_witness']['uncompressed_bytes'])] + [
                (step['snapshot']['sha256'], step['snapshot']['bytes']) for step in pair['steps']]
            for revision, (command, (identity, size)) in enumerate(zip(direct['commands'], expected_inputs)):
                require(command['revision'] == revision and command['snapshot']['sha256'] == identity and
                        command['snapshot']['bytes'] == size and command['snapshot']['seals'] & 15 == 15,
                        'uninterrupted fresh Rust does not read each identical fully sealed revision')
                command_ok(command, command['snapshot'], full_binary)
            require(direct['wall_seconds'] >= sum(command['wall_seconds'] for command in direct['commands']),
                    'uninterrupted direct outer wall improperly omits command execution')
            for blob in candidate['compressed_session_files']:
                archive_check(blob)
            arithmetic_checks += 1
        validate_export_coverage(actual_inputs, witnessed_inputs)
        economics = paired_economics([dict(
            apply_wall_seconds=pair['components']['api_component_sum_wall_seconds'],
            direct_wall_seconds=pair['components']['direct_full_rust_component_sum_wall_seconds']) for pair in pairs], seed=20261022)
        economics.update(scope=report['measurement_policy']['primary'], comparator=report['measurement_policy']['direct'],
                         setup_in_timed_update=True,
                         accepted_revisions_per_pair=expected_revisions, paired_sequences=len(pairs),
                         claim_status='QUALIFICATION_REQUIRES_FIVE_EXACT_PAIRED_LIFETIMES' if len(pairs) < 5 else 'OBSERVED_COMPONENT_SUMS')
        if len(pairs) < 5:
            economics.update(observed_status=economics['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
        for key, value in economics.items():
            require(profile_report['economics'].get(key) == value, 'lifetime economic arithmetic changed: ' + key)
        cpu_economics = paired_economics([dict(
            apply_wall_seconds=pair['cpu_components']['api_component_sum_cpu_seconds'],
            direct_wall_seconds=pair['cpu_components']['direct_full_rust_component_sum_cpu_seconds']) for pair in pairs], seed=20261023)
        cpu_economics.update(scope=pairs[0]['cpu_components']['scope'], measurement='cpu_seconds', setup_in_timed_update=True)
        if len(pairs) < 5:
            cpu_economics.update(observed_status=cpu_economics['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
        for key, value in cpu_economics.items():
            require(profile_report['cpu_economics'].get(key) == value, 'lifetime CPU economic arithmetic changed: ' + key)
        for name, field, seed in (('continuous_economics', 'wall_seconds', 20261024),
                                  ('continuous_cpu_economics', 'cpu_seconds', 20261025)):
            measured = paired_economics([dict(apply_wall_seconds=p['continuous']['candidate'][field],
                direct_wall_seconds=p['continuous']['direct'][field]) for p in pairs], seed=seed)
            measured.update(scope=report['measurement_policy']['continuous_primary'],
                            comparator=report['measurement_policy']['continuous_direct'],
                            measurement=field, setup_in_timed_update=True,
                            accepted_revisions_per_pair=expected_revisions, paired_sequences=len(pairs))
            if len(pairs) < 5:
                measured.update(observed_status=measured['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
            require(canonical(profile_report[name]) == canonical(measured), 'uninterrupted paired economic arithmetic changed: ' + name)
        require(len(profile_report['revision_economics']) == expected_revisions, 'missing per-revision observed economics')
        for revision, entry in enumerate(profile_report['revision_economics']):
            economics = paired_economics([dict(apply_wall_seconds=p['steps'][revision]['apply_wall_seconds'],
                direct_wall_seconds=p['steps'][revision]['direct_rust']['wall_seconds']) for p in pairs], seed=20261022 + revision)
            if len(pairs) < 5:
                economics.update(observed_status=economics['status'], status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
            require(entry['revision'] == revision + 1 and canonical(entry['economics']) == canonical(economics),
                    'per-revision economic arithmetic changed')
    return dict(status='PASS_SMOKE_EVIDENCE_UNQUALIFIED' if allow_smoke else 'PASS_EXACT_REVISION_LIFETIME_EVIDENCE', source_sha=expected_source,
                paired_lifetimes=arithmetic_checks, accepted_revisions=arithmetic_checks * expected_revisions,
                historical_hmac_reauthenticated=False, summary_sha256=file_hash(path),
                scope='Actual full-index/selected-set replay, exact-byte command/result/receipt witnesses and raw economics; issuer HMAC validity observed from private-key run.')


def self_test():
    class RevisionMeasurementContracts(unittest.TestCase):
        def feature(self, name):
            self.assertTrue(callable(globals().get(name)), "missing revision benchmark capability: " + name)
            return globals()[name]

        def test_cumulative_sequence_restores_each_body_against_immediate_parent(self):
            from build_workloads import EDITS
            sources = {"IncrementalWorkload/Base.lean": EDITS['early-definition'][1],
                       "IncrementalWorkload/Leaves.lean": EDITS['unrelated-definition'][1]}
            plan = self.feature('revision_plan')(sources, 2)
            self.assertEqual(len(plan), 8)
            self.assertIn(EDITS['early-definition'][2], plan[1]['sources'][EDITS['early-definition'][0]])
            self.assertIn(EDITS['unrelated-definition'][2], plan[1]['sources'][EDITS['unrelated-definition'][0]])
            self.assertEqual(plan[3]['sources'], sources)
            self.assertEqual(plan[7]['sources'], sources)
            self.assertEqual([s['state'] for s in plan], [1, 2, 3, 0] * 2)
            self.assertEqual(plan[2]['patch'][1:], EDITS['early-definition'][1:][::-1])

        def test_lifetime_uses_measured_intervals_and_charges_genesis_fresh_check(self):
            measured = self.feature('lifecycle_components')(2.0, [0.2, 0.3], 0.1, 0.8, [0.9, 1.1])
            self.assertAlmostEqual(measured['api_component_sum_wall_seconds'], 2.6)
            self.assertAlmostEqual(measured['direct_full_rust_component_sum_wall_seconds'], 2.8)
            self.assertEqual(measured['accepted_revisions'], 2)
            self.assertNotIn('break_even_updates', measured)
            with self.assertRaises(ValueError):
                globals()['lifecycle_components'](2.0, [float('nan')], 0.1, 1.0, [1.0])
            with self.assertRaises(ValueError):
                globals()['lifecycle_components'](2.0, [0.2], 0.1, 1.0, [])

        def test_link_audit_refuses_skipped_revision_parent_or_missing_capture(self):
            good = dict(status='VERIFIED', evidence_id='d' * 64, previous_evidence='a' * 64,
                        revision_chain=dict(head_id='e' * 64, revision=3, parent_head='b' * 64,
                                            parent_evidence='a' * 64, source_capture_id='c' * 64))
            audit = self.feature('validate_link')
            self.assertEqual(audit(good, 'b' * 64, 'a' * 64, 3)['revision'], 3)
            for field, value in [('revision', 4), ('parent_head', 'f' * 64),
                                 ('parent_evidence', 'f' * 64), ('source_capture_id', None)]:
                broken = json.loads(json.dumps(good)); broken['revision_chain'][field] = value
                with self.assertRaises(ValueError):
                    audit(broken, 'b' * 64, 'a' * 64, 3)

        def test_summary_verifier_does_not_accept_empty_or_unqualified_claim(self):
            verify = self.feature('verify_summary')
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'summary.json'
                for report in ({}, dict(schema=SCHEMA, completed=True, correctness_passed=True,
                                        qualified=False, source_sha='a' * 40)):
                    path.write_text(json.dumps(report))
                    with self.assertRaises(ValueError):
                        verify(path, 'a' * 40)

        def test_cpu_lifetime_uses_its_own_observed_cpu_components(self):
            measured = self.feature('lifecycle_cpu_components')(1.0, [0.2, 0.3], 0.1, 0.4, [0.8, 0.9])
            self.assertAlmostEqual(measured['api_component_sum_cpu_seconds'], 1.6)
            self.assertAlmostEqual(measured['direct_full_rust_component_sum_cpu_seconds'], 2.1)
            self.assertIn('SC_CLK_TCK', measured['scope'])

        def test_smoke_reader_refuses_zero_work_and_empty_identity_manifests(self):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'summary.json'
                source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
                report = dict(schema=SCHEMA, source_sha=source, completed=True, correctness_passed=True,
                              source_and_binary_stable=True, source_sha256={}, profiles={}, repetitions=0, cycles=0,
                              binary_sha256={'full_checker': dict(path='/bin/true', sha256=file_hash('/bin/true'))})
                path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    verify_summary(path, source, allow_smoke=True)

        def test_conflicting_repeated_archive_descriptor_is_refused(self):
            check = self.feature('archive_descriptor')
            record = dict(sha256='a' * 64, bytes=30, encoding='gzip', uncompressed_sha256='b' * 64, uncompressed_bytes=10)
            self.assertEqual(check(record), ('a' * 64, 30, 'b' * 64, 10))
            with self.assertRaises(ValueError):
                check(dict(record, uncompressed_bytes=-1))
            with self.assertRaises(ValueError):
                check(dict(record, uncompressed_bytes=11), check(record))

        def test_complete_export_coverage_is_required_for_each_actual_input(self):
            check = self.feature('validate_export_coverage')
            self.assertIsNone(check({('a' * 64, 10)}, {('a' * 64, 10)}))
            with self.assertRaises(ValueError):
                check({('a' * 64, 10), ('b' * 64, 20)}, {('a' * 64, 10)})

        def test_continuous_arm_binds_actual_counts_and_input_to_independent_arm(self):
            check = self.feature('compact_continuous_result')
            expected = dict(source_root='b' * 64, snapshot=dict(sha256='a' * 64, bytes=20),
                            partition_audit=dict(actual_kernel_total=3, actual_kernel_checked=1,
                                                 independently_replayed_reused=2, checked_indices=[0]))
            actual = dict(status='VERIFIED', export_sha256='a' * 64,
                          representation=dict(export_bytes=20),
                          counts=dict(total=3, scheduled=1, rechecked=1, reused=2, invalidated=1),
                          native_kernel_report=dict(status='checked', code=0, checked=1, total_declarations=3))
            for field in ('evidence_id', 'previous_evidence', 'revision_chain', 'producer_provenance', 'checker_result', 'timings'):
                actual[field] = {} if field not in ('evidence_id', 'previous_evidence') else 'c' * 64
            self.assertEqual(check(actual, expected, 'b' * 64)['snapshot_bytes'], 20)
            actual['counts']['rechecked'] = 2
            with self.assertRaises(ValueError):
                check(actual, expected, 'b' * 64)

    return unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RevisionMeasurementContracts)).wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--verify-summary', type=Path)
    parser.add_argument('--verify-smoke-summary', type=Path, help='Review complete actual smoke evidence without qualifying its economics.')
    parser.add_argument('--expected-source')
    for name in ('original-workloads', 'expanded-workloads', 'producer', 'checker',
                 'retained-checker', 'indexer', 'index-session', 'full-checker', 'authority-key', 'out'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--profiles', nargs='+', choices=('original', 'expanded'), default=['original', 'expanded'])
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--smoke', action='store_true', help='Preserve actual smaller/dirty correctness observations without qualification claims.')
    args = parser.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    if args.verify_summary or args.verify_smoke_summary:
        require(args.expected_source is not None, '--verify-summary requires explicit expected source SHA')
        print(json.dumps(verify_summary(args.verify_summary or args.verify_smoke_summary, args.expected_source,
                                        allow_smoke=args.verify_smoke_summary is not None)))
        return 0
    for name in ('original_workloads', 'expanded_workloads', 'producer', 'checker',
                 'retained_checker', 'indexer', 'index_session', 'full_checker', 'authority_key', 'out'):
        require(getattr(args, name) is not None, 'missing required --' + name.replace('_', '-'))
        setattr(args, name, getattr(args, name).resolve())
    require(args.repetitions > 0 and args.cycles > 0 and len(set(args.profiles)) == len(args.profiles),
            'positive repetitions/cycles and unique profiles required')
    if not args.smoke:
        require(args.repetitions == 5 and args.cycles == 10 and set(args.profiles) == {'original', 'expanded'},
                'qualification requires exactly five paired forty-revision lifetimes on both profiles; use --smoke for smaller observations')
    run(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
