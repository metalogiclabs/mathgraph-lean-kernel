#!/usr/bin/env python3
"""Real-kernel adversarial controls for authenticated delta-state receipts.

All warm decisions use the real source owner, native typed index and retained
kernel. Explicit full exports below are independent audits outside update time.
An unaccepted attempted export never supplies reusable evidence.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import engine
from authenticated_state import (STATE_ACCEPTANCE, STATE_TRANSITION,
                                 StateChainSession, authenticate_state_acceptance)
from producer_delta import (TRANSITION, authenticate_sparse_acceptance, seal,
                            sha, sources_at)
from qualify_delta import (audit_partition, command_run, configuration,
                           fresh_index, selected_report, write)


REQUIRED_CONTROLS = (
    'verified-baseline-independent-oracles',
    'early-edit-full-index-partition-and-kernel-parity',
    'returned-source-capture-does-not-alias-accepted-state',
    'unchanged-zero-selected-real-parser-no-full-export',
    'unused-valid-dag-zero-selected-real-parser',
    'issuer-injected-unused-dag-history-refuses-cold-replay',
    'forged-hmac', 'changed-delta-without-authority',
    'dropped-authenticated-replacement', 'reordered-delta-without-authority',
    'duplicate-authenticated-replacement', 'unterminated-authenticated-delta',
    'source-capture-patch-substitution', 'source-capture-names-substitution',
    'authenticated-wrong-evidence-parent', 'authenticated-wrong-state-parent',
    'authenticated-environment-drift', 'authenticated-version-drift',
    'foreign-transition-domain', 'authenticated-metadata-drift',
    'source-outside-reported-region', 'false-change-name-hint',
    'axiom-kind-assumption-change', 'invalid-source-proof',
    'toolchain-source-outside-policy', 'changed-unused-admitted-dag',
    'unused-malformed-dag-zero-selected', 'signed-invalid-definition-proof',
    'foreign-issuer', 'receipt-policy-version-mismatch',
    'corrupt-chain-head', 'corrupt-source-capture', 'corrupt-current-receipt',
    'corrupt-transition', 'corrupt-delta', 'corrupt-state-representation',
    'corrupt-genesis-state', 'corrupt-genesis', 'corrupt-baseline-receipt',
    'corrupt-baseline-export', 'deleted-latest-head-no-prefix-fallback',
    'cold-start-requires-external-expected-head', 'wrong-external-expected-head',
    'state-receipt-rejected-by-full-export-domain',
    'state-receipt-rejected-by-sparse-export-domain',
    'full-export-receipt-rejected-by-state-domain',
    'failed-receipt-persistence-does-not-promote-state',
    'failed-persistence-does-not-promote-state',
    'cold-recovery-and-dependency-restoration',
    'real-dependency-edge-fallback-refresh-and-restore')


def compact(result):
    if result is None:
        return None
    value = {key: result[key] for key in ('schema', 'status', 'evidence_id',
        'state_id', 'export_sha256', 'counts', 'reason', 'checker_result',
        'representation', 'timings', 'revision_chain') if key in result}
    if 'typed_update' in result:
        value['typed_update_summary'] = {k:v for k,v in result['typed_update'].items()
                                         if k not in ('index','index_patch')}
    return value


def run(args):
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('controls require fresh evidence output')
    out.mkdir(parents=True, exist_ok=True)
    args.workloads, args.binaries, args.producer = (
        p.resolve() for p in (args.workloads, args.binaries, args.producer))
    manifest = json.loads((args.workloads / 'manifest.json').read_bytes())
    report = dict(schema='mathgraph.authenticated-state-controls.v1', passed=False,
        source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        profile=manifest.get('profile', 'original-v1'), controls=[],
        required_controls=list(REQUIRED_CONTROLS),
        adversary_scope='key-resigned parser falsifiers possess issuer authority; '
                        'separate forged-HMAC controls exercise unauthenticated attackers; '
                        'injected bytes are not claimed to be source-producer output')

    def record(name, **detail):
        assert name in REQUIRED_CONTROLS, name
        assert not any(row['name'] == name for row in report['controls']), name
        report['controls'].append(dict(name=name, passed=True, **detail))
        write(out / 'summary.json', report)

    def preserve_export(path, name):
        target = out / 'inputs' / (name + '.ndjson.gz')
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        count = 0
        with Path(path).open('rb') as reader, gzip.open(target, 'wb') as writer:
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
                count += len(chunk)
                writer.write(chunk)
        return dict(path=str(target), export_sha256=digest.hexdigest(), export_bytes=count)

    def oracles(export, name, code, all_kernels=True):
        config = out / name / 'config.json'
        write(config, configuration(export))
        commands = [('rust', [args.binaries / 'sokonanoda', config])]
        if all_kernels:
            commands.extend((label, [manifest['tools'][label]['path'], '--from-export', export])
                for label in ('leanchecker', 'leanchecker-paranoid'))
        observed = {}
        for label, command in commands:
            process, _ = command_run(command, out / name / label)
            assert process['returncode'] == code and not process['timed_out'], (name, label, process)
            observed[label] = process
        return observed

    initial = sources_at(args.workloads / 'baseline' / 'source')
    source = out / 'live-source'

    def put_sources(sources):
        for name, text in sources.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def edit_source(change):
        filename, before, after = change
        path = source / filename
        text = path.read_text()
        assert before in text, (filename, before)
        path.write_text(text.replace(before, after))

    # Gather only the tiny witnesses needed by adversaries, not a second full
    # parsed copy of the 64 MB export in the expanded profile.
    baseline_path = Path(manifest['variants']['baseline']['path'])
    names, exprmax, sortzero, early = {0: ''}, 0, None, None
    for line in baseline_path.open('rb'):
        row = json.loads(line)
        if 'in' in row:
            part = row.get('str', row.get('num'))
            prefix = names[part['pre']]
            names[row['in']] = (prefix + '.' if prefix else '') + str(part.get('str', part.get('i')))
        if 'ie' in row:
            exprmax = max(exprmax, row['ie'])
            if row.get('sort') == 0:
                sortzero = row['ie']
        if 'def' in row and names[row['def']['name']] == 'IncrementalWorkload.early':
            early = row
    assert early is not None and sortzero is not None
    unused_id = exprmax + 100

    with tempfile.TemporaryDirectory(prefix='state-controls-authority-') as private:
        key = Path(private) / 'issuer.key'
        key.write_bytes(os.urandom(32))
        key.chmod(0o600)
        state = out / 'state'

        def session(**overrides):
            kwargs = dict(root=state, workloads=args.workloads, producer=args.producer,
                checker=args.binaries / 'check-selected', indexer=args.binaries / 'export-index',
                index_session=args.binaries / 'index-session', authority_key=key,
                retained_checker=args.binaries / 'check-selected-retained-session')
            kwargs.update(overrides)
            return StateChainSession(**kwargs)

        def resign(transaction, live, delta):
            transaction['delta_bytes'] = delta
            payload = copy.deepcopy(transaction['attestation']['payload'])
            payload['delta_sha256'] = sha(delta)
            transaction['attestation'] = seal(payload, live.key)
            transaction['_control_authority_scope'] = 'issuer-authorized-parser-falsifier'

        def prepared(live):
            return live.prepare(source, None, [])

        def changed(live):
            change = ('IncrementalWorkload/Base.lean', 'def early : Nat := 23',
                      'def early : Nat := 29')
            edit_source(change)
            return live.prepare(source, change, ['IncrementalWorkload.early'])

        put_sources(initial)
        with session() as live:
            ready = live.start()
            baseline_index = copy.deepcopy(live.old['index'])
            baseline = preserve_export(baseline_path, 'baseline')
            assert baseline['export_sha256'] == live.export_pins['baseline']
            record('verified-baseline-independent-oracles', ready=ready,
                baseline=baseline, independent_kernel_acceptances=oracles(baseline_path, 'baseline', 0))
            change = ('IncrementalWorkload/Base.lean', 'def early : Nat := 17',
                      'def early : Nat := 23')
            edit_source(change)
            with patch('os.memfd_create', side_effect=AssertionError('warm state materialized full export')):
                first = live.apply(source, change, ['IncrementalWorkload.early'])
            assert first['status'] == 'VERIFIED' and first['export_sha256'] is None, compact(first)
            exported = live.materialize_current()
            fresh, _ = fresh_index(exported['path'], args.binaries / 'export-index', out / 'fresh-first')
            partition = audit_partition(first, baseline_index, fresh)
            assert engine.encoded(fresh) == engine.encoded(live.old['index'])
            record('early-edit-full-index-partition-and-kernel-parity', result=compact(first),
                partition=partition, audit=live.audit_current_acceptance(fresh),
                exact_input=preserve_export(exported['path'], 'early-edit'),
                independent_kernel_acceptances=oracles(exported['path'], 'early-edit', 0))
            live.last_transaction['source_capture']['sources'][change[0]] = 'forged after acceptance'
            assert live.baseline_sources[change[0]] == (source / change[0]).read_text()
            record('returned-source-capture-does-not-alias-accepted-state')
            with patch('os.memfd_create', side_effect=AssertionError('unchanged full export')):
                unchanged = live.apply(source, None, [])
            assert unchanged['status'] == 'VERIFIED' and unchanged['counts']['scheduled'] == 0
            assert selected_report(unchanged)['checked'] == 0
            assert live.snapshot_path is None
            record('unchanged-zero-selected-real-parser-no-full-export', result=compact(unchanged),
                real_parser_report=unchanged['native_kernel_report'])
            # The following issuer-authorized row is deliberately not emitted
            # by the source producer. Keep the genuine producer head as our
            # cold authority; injected history must not be silently repaired.
            head, evidence, state_id = live.head_id, live.base_id, live.state_id
            accepted = dict(live.baseline_sources)
            accepted_result = compact(unchanged)
            saved_parent = live.last_parent_record
            saved_parent_state = live._parent_state(saved_parent, live.last_parent_evidence_id)
            genesis_state_id = live.genesis_state_id
            accepted_history_heads = {live.genesis_head,first['revision_chain']['head_id'],head}
            transaction = prepared(live)
            resign(transaction, live, engine.encoded(dict(ie=unused_id, bvar=0)) + b'\n')
            with patch('os.memfd_create', side_effect=AssertionError('unused node full export')):
                unused = live.validate_apply(transaction)
            assert unused['status'] == 'VERIFIED' and unused['counts']['scheduled'] == 0, compact(unused)
            assert selected_report(unused)['checked'] == 0
            assert live.snapshot_path is None
            exported = live.materialize_current()
            unused_index, _ = fresh_index(exported['path'], args.binaries / 'export-index', out / 'fresh-unused')
            assert engine.encoded(unused_index) == engine.encoded(fresh)
            record('unused-valid-dag-zero-selected-real-parser', result=compact(unused),
                authority_scope='issuer-authorized-parser-falsifier;not-genuine-producer-output',
                real_parser_report=unused['native_kernel_report'],
                exact_input=preserve_export(exported['path'], 'unused-valid'),
                independent_kernel_acceptances=oracles(exported['path'], 'unused-valid', 0))
            injected_head, injected_evidence, injected_state = live.head_id, live.base_id, live.state_id
            before = sorted(path.name for path in (state/'cache'/'records').glob('*.json'))
            transaction = prepared(live)
            resign(transaction,live,engine.encoded(dict(ie=unused_id,bvar=1))+b'\n')
            try:
                result = live.validate_apply(transaction)
            except (ValueError,KeyError,OSError,TypeError) as error:
                observed = str(error)
            else:
                assert result['status'] in ('UNKNOWN','REJECTED'),compact(result)
                observed = result.get('reason','')
            assert live.poisoned and live.head_id == injected_head and live.state_id == injected_state
            assert live.snapshot_path is None and live._proposed_recipe is None
            assert before == sorted(path.name for path in (state/'cache'/'records').glob('*.json'))
            delta_path = out/'negative-deltas'/'changed-unused-admitted-dag.ndjson'
            delta_path.parent.mkdir(parents=True,exist_ok=True)
            delta_path.write_bytes(transaction['delta_bytes'])
            attestation_path = delta_path.with_suffix('.attestation.json')
            write(attestation_path,transaction['attestation'])
            record('changed-unused-admitted-dag',observed_refusal=observed,
                poisoned=True,accepted_records_unchanged=True,
                refusal_boundary='before_staged_recipe;actual_delta_preserved',
                actual_delta=dict(path=str(delta_path),sha256=sha(transaction['delta_bytes']),
                    attestation_path=str(attestation_path),parent_state_id=injected_state,
                    parent_evidence_id=injected_evidence),
                authority_scope='issuer-authorized-parser-falsifier;not-genuine-producer-output')

        def records():
            return sorted(path.name for path in (state / 'cache' / 'records').glob('*.json'))

        def refusal(name, action, reason=None, overrides=None, kernel=False, expected_head=None):
            put_sources(accepted)
            before = records()
            with session(**(overrides or {})) as live:
                observed, result = None, None
                try:
                    live.start(expected_head=head if expected_head is None else expected_head)
                    result = action(live)
                    if result is not None and result.get('status') in ('UNKNOWN', 'REJECTED'):
                        observed = result.get('reason', result.get('checker_result', {}).get('stderr', ''))
                except (ValueError, KeyError, OSError, TypeError) as error:
                    observed = str(error)
                assert observed is not None, (name, 'accepted or did not refuse', compact(result))
                if reason is not None:
                    assert reason in observed, (name, observed)
                assert live.poisoned and all(process is None or process.process.poll() is not None
                    for process in (live.producer, live.index, live.kernel_process)), name
                assert records() == before, (name, 'persisted acceptance after refusal')
                assert live.head_id is None or live.head_id in accepted_history_heads, (name,live.head_id)
                assert live.snapshot_path is None, (name, 'stale or implicit successor export')
                detail = dict(observed_refusal=observed, accepted_records_unchanged=True,
                              poisoned=True, result=compact(result))
                transaction = getattr(live, '_adversarial_transaction', None)
                if transaction is not None:
                    delta_path = out/'negative-deltas'/(name+'.ndjson')
                    delta_path.parent.mkdir(parents=True, exist_ok=True)
                    delta_path.write_bytes(transaction['delta_bytes'])
                    attestation_path = delta_path.with_suffix('.attestation.json')
                    write(attestation_path, transaction['attestation'])
                    detail['actual_delta'] = dict(path=str(delta_path),
                        sha256=sha(transaction['delta_bytes']),
                        attestation_path=str(attestation_path), parent_state_id=state_id,
                        parent_evidence_id=evidence)
                    detail['authority_scope'] = transaction.get('_control_authority_scope',
                        'modified transaction without valid issuer authentication')
                    if getattr(live, '_proposed_recipe', None) is None:
                        try:
                            live.materialize_attempt()
                        except ValueError:
                            pass
                        else:
                            raise AssertionError((name,'unparsed candidate acquired an export'))
                        detail['refusal_boundary'] = 'before_staged_recipe;actual_delta_preserved'
                if kernel:
                    assert result is not None and result['status'] == 'REJECTED'
                    assert result['checker_result']['code'] == 1, compact(result)
                    attempt = live.materialize_attempt()
                    assert attempt['state_id'] is None and attempt['parent_state_id'] == state_id
                    assert attempt['scope'] == 'unaccepted_attempt_for_independent_oracle_only'
                    saved = preserve_export(attempt['path'], name)
                    assert saved['export_sha256'] == attempt['export_sha256']
                    assert saved['export_bytes'] == attempt['export_bytes']
                    detail.update(independent_kernel_rejections=oracles(attempt['path'], name, 1),
                        exact_negative_export_sha256=attempt['export_sha256'],
                        exact_negative_export=saved,
                        attempt_identity={k:v for k,v in attempt.items() if k not in
                                          ('path','wall_seconds','cpu_seconds','seals')})
                record(name, **detail)

        def altered(live, mutation, needs_change=False):
            transaction = changed(live) if needs_change else prepared(live)
            mutation(transaction, live)
            live._adversarial_transaction = transaction
            return live.validate_apply(transaction)

        refusal('issuer-injected-unused-dag-history-refuses-cold-replay',lambda _: None,
                'cold producer delta history mismatch',expected_head=injected_head)
        refusal('forged-hmac', lambda s: altered(s,
            lambda t,_: t['attestation'].__setitem__('hmac_sha256', '0' * 64)), 'issuer authentication failed')
        refusal('changed-delta-without-authority', lambda s: altered(s,
            lambda t,_: t.__setitem__('delta_bytes', b'{}\n')), 'changed-byte integrity failed')
        refusal('dropped-authenticated-replacement', lambda s: altered(s,
            lambda t,s: resign(t,s,b''), True))
        def reordered(live):
            change = ('IncrementalWorkload/Base.lean',
                'def early : Nat := 23\n\ndef typed : Nat := 7',
                'def early : Nat := 29\n\ndef typed : Nat := 11')
            edit_source(change)
            transaction = live.prepare(source,change,['IncrementalWorkload.early','IncrementalWorkload.typed'])
            rows = transaction['delta_bytes'].splitlines(keepends=True)
            assert len(rows) >= 2
            transaction['delta_bytes'] = b''.join(reversed(rows))
            live._adversarial_transaction = transaction
            return live.validate_apply(transaction)
        refusal('reordered-delta-without-authority',reordered,'changed-byte integrity failed')
        def duplicate(transaction, live):
            declaration = next(raw for raw in transaction['delta_bytes'].splitlines(keepends=True)
                               if set(json.loads(raw)) & engine.SIMPLE)
            resign(transaction, live, transaction['delta_bytes'] + declaration)
        refusal('duplicate-authenticated-replacement', lambda s: altered(s, duplicate, True))
        refusal('unterminated-authenticated-delta', lambda s: altered(s,
            lambda t,s: resign(t,s,t['delta_bytes'].removesuffix(b'\n')), True))
        refusal('source-capture-patch-substitution', lambda s: altered(s,
            lambda t,_: t['source_capture'].__setitem__('patch', ['bad','x','y'])),
            'prepared complete source capture was modified')
        refusal('source-capture-names-substitution', lambda s: altered(s,
            lambda t,_: t['source_capture'].__setitem__('claimed_names', ['bad'])),
            'prepared complete source capture was modified')
        for name, field, value in (
            ('authenticated-wrong-evidence-parent', 'base_evidence_id', '0' * 64),
            ('authenticated-wrong-state-parent', 'base_state_id', '0' * 64),
            ('authenticated-environment-drift', 'baseline_source_root', '0' * 64),
            ('authenticated-version-drift', 'provenance', {'schema':'foreign'}),
            ('foreign-transition-domain', 'schema', TRANSITION)):
            def mutation(t,s,field=field,value=value):
                payload = copy.deepcopy(t['attestation']['payload'])
                payload[field] = value
                t['attestation'] = seal(payload,s.key)
            refusal(name, lambda s,mutation=mutation: altered(s,mutation))
        refusal('authenticated-metadata-drift', lambda s: altered(s,
            lambda t,s: resign(t,s,engine.encoded({'meta':{'schema':'foreign'}})+b'\n')))
        def outside(live):
            edit_source(('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 99'))
            return live.apply(source,None,[])
        refusal('source-outside-reported-region',outside,'source modifications outside the reported patch')
        def wrong_names(live):
            change = ('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5')
            edit_source(change)
            return live.apply(source,change,[])
        refusal('false-change-name-hint',wrong_names,'expected_changed_names differs from complete local comparison')
        def axiom_change(live):
            change = ('IncrementalWorkload/Base.lean','def typed : Nat := 7','axiom typed : Nat')
            edit_source(change)
            return live.apply(source,change,['IncrementalWorkload.typed'])
        refusal('axiom-kind-assumption-change',axiom_change,'metadata/kind drift')
        def invalid_source(live):
            change = ('IncrementalWorkload/Leaves.lean','Eq.refl n','Nat.zero')
            edit_source(change)
            return live.apply(source,change,['IncrementalWorkload.leaf'])
        refusal('invalid-source-proof',invalid_source)
        def toolchain(live):
            path = source / 'lean-toolchain'
            path.write_text(path.read_text()+'\n')
            return live.apply(source,None,[])
        refusal('toolchain-source-outside-policy',toolchain,'source modifications outside the reported patch')
        refusal('unused-malformed-dag-zero-selected',lambda s: altered(s,
            lambda t,s: resign(t,s,engine.encoded(dict(ie=unused_id+1,bvar='not-an-integer'))+b'\n')),
            kernel=True)
        bad = copy.deepcopy(early)
        bad['def']['value'] = sortzero
        refusal('signed-invalid-definition-proof',lambda s: altered(s,
            lambda t,s: resign(t,s,engine.encoded(bad)+b'\n'),True),kernel=True)
        wrong_key = Path(private) / 'foreign.key'
        wrong_key.write_bytes(os.urandom(32))
        refusal('foreign-issuer',lambda _: None,'evidence issuer authentication failed',dict(authority_key=wrong_key))
        refusal('receipt-policy-version-mismatch',lambda _: None,'source-owner genesis provenance mismatch',
                dict(receipt_index_comparison='canonical_json'))

        state_info = json.loads((state / 'session-state.json').read_bytes())
        receipt_path = state / 'cache' / 'records' / (evidence + '.json')
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw)['payload']
        representation_path = state / 'cache' / 'representations' / (receipt['state_id']+'.json')
        representation = json.loads(representation_path.read_bytes())
        targets = {
            'corrupt-chain-head': state/'cache'/'chain'/(head+'.json'),
            'corrupt-source-capture': state/'cache'/'source-captures'/(accepted_result['revision_chain']['source_capture_id']+'.json'),
            'corrupt-current-receipt': receipt_path,
            'corrupt-transition': state/'cache'/'transitions'/(representation['transition_id']+'.json'),
            'corrupt-delta': state/'cache'/'deltas'/(representation['delta_sha256']+'.ndjson'),
            'corrupt-state-representation': representation_path,
            'corrupt-genesis-state': state/'cache'/'representations'/(genesis_state_id+'.json'),
            'corrupt-genesis': state/'cache'/'genesis'/(state_info['genesis_id']+'.json'),
            'corrupt-baseline-receipt': state/'baseline-cache'/'records'/(state_info['base_evidence_id']+'.json'),
            'corrupt-baseline-export': next((state/'baseline-cache'/'exports').glob('*.ndjson'))}
        for name,path in targets.items():
            raw = path.read_bytes()
            path.chmod(0o644)
            path.write_bytes(raw+b'corrupt')
            try:
                refusal(name,lambda _: None)
                corrupted = out/'corruptions'/(name+'.gz')
                corrupted.parent.mkdir(parents=True,exist_ok=True)
                with gzip.open(corrupted,'wb') as writer:
                    writer.write(path.read_bytes())
                report['controls'][-1]['corrupted_object'] = dict(path=str(corrupted),
                    original_content_sha256=sha(raw), corrupted_content_sha256=sha(raw+b'corrupt'),
                    immutable_object_path=str(path))
                write(out/'summary.json',report)
            finally:
                path.write_bytes(raw)
                path.chmod(0o444)
        path = targets['corrupt-chain-head']
        raw = path.read_bytes()
        path.unlink()
        try:
            refusal('deleted-latest-head-no-prefix-fallback',lambda _: None)
        finally:
            engine.immutable_write(path,raw)
        put_sources(accepted)
        with session() as live:
            try:
                live.start()
            except ValueError as error:
                assert 'requires caller expected head' in str(error)
            else:
                raise AssertionError('inferred latest state from ordinary cache')
            assert live.poisoned
            record('cold-start-requires-external-expected-head')
        refusal('wrong-external-expected-head',lambda _: None,expected_head='0'*64)
        baseline_receipt = targets['corrupt-baseline-receipt'].read_bytes()
        cross_domains = (
            ('state-receipt-rejected-by-full-export-domain',
             lambda: engine.authenticate_record(receipt_raw,evidence,key.read_bytes())),
            ('state-receipt-rejected-by-sparse-export-domain',
             lambda: authenticate_sparse_acceptance(receipt_raw,evidence,key.read_bytes(),saved_parent)),
            ('full-export-receipt-rejected-by-state-domain',
             lambda: authenticate_state_acceptance(baseline_receipt,sha(baseline_receipt),
                                                    key.read_bytes(),saved_parent,saved_parent_state)))
        for name,action in cross_domains:
            try:
                action()
            except (ValueError,KeyError,TypeError) as error:
                record(name,observed_refusal=str(error),state_domain=STATE_ACCEPTANCE)
            else:
                raise AssertionError((name,'cross-domain evidence accepted'))

        for category,name in (
            ('records','failed-receipt-persistence-does-not-promote-state'),
            ('chain','failed-persistence-does-not-promote-state')):
            put_sources(accepted)
            with session() as failed:
                failed.start(expected_head=head)
                old_recipe = failed.recipe
                original_put = failed._put
                def fail_put(current,raw,suffix):
                    if current == category:
                        raise OSError('injected '+category+' persistence failure')
                    return original_put(current,raw,suffix)
                failed._put = fail_put
                change = ('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5')
                edit_source(change)
                result = failed.apply(source,change,['IncrementalWorkload.unrelated'])
                assert result['status'] == 'UNKNOWN' and result['evidence_id'] is None and failed.poisoned
                assert failed.head_id == head and failed.base_id == evidence and failed.state_id == state_id
                assert failed.recipe is old_recipe and failed.snapshot_path is None
                again = failed.apply(source,None,[])
                assert again['status'] == 'UNKNOWN' and failed.head_id == head and failed.state_id == state_id
                record(name,result=compact(result),injected_category=category,
                    historical_orphan_receipt_only_after_genuine_kernel_acceptance=True,
                    expected_head_and_state_unchanged=True,unchanged_recipe_object=True,
                    subsequent_in_place_update_refused=True)

        put_sources(accepted)
        with session() as restored:
            restarted = restored.start(expected_head=head)
            assert restored.base_id == evidence and restored.head_id == head and restored.state_id == state_id
            assert restarted['replayed_revisions'] == 2
            change = ('IncrementalWorkload/Base.lean','def early : Nat := 23','def early : Nat := 17')
            edit_source(change)
            result = restored.apply(source,change,['IncrementalWorkload.early'])
            assert result['status'] == 'VERIFIED',compact(result)
            exported = restored.materialize_current()
            previous,_ = fresh_index(exported['path'],args.binaries/'export-index',out/'fresh-restored')
            assert engine.encoded(previous) == engine.encoded(baseline_index)
            audit_partition(result,restored.last_parent_record['index'],previous)
            assert restored.source_root == engine.digest(initial)
            record('cold-recovery-and-dependency-restoration',replayed_revisions=2,
                restored_semantic_index=True,
                export_sha256_equal_to_baseline=exported['export_sha256']==restored.export_pins['baseline'],
                exact_input=preserve_export(exported['path'],'restored'),
                independent_kernel_acceptances=oracles(exported['path'],'restored',0))
            transitions = []
            for change,name,fallback in (
                (('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + IncrementalWorkload.early'),'unrelated',True),
                (('IncrementalWorkload/Base.lean','def early : Nat := 17','def early : Nat := 31'),'early',False),
                (('IncrementalWorkload/Leaves.lean','n * n + IncrementalWorkload.early','n * n + 3'),'unrelated',True),
                (('IncrementalWorkload/Base.lean','def early : Nat := 31','def early : Nat := 17'),'early',False)):
                edit_source(change)
                with patch('os.memfd_create',side_effect=AssertionError('topology fallback materialized full export')):
                    result = restored.apply(source,change,['IncrementalWorkload.'+name])
                assert result['status'] == 'VERIFIED',compact(result)
                assert result['typed_update']['retained_graph_used'] is (not fallback),result['typed_update']
                assert result['typed_update']['index_wire'] == ('full_index_v1' if fallback else 'baseline_patch_v1')
                exported = restored.materialize_current()
                folder = out/'edge-transitions'/str(len(transitions))
                current,_ = fresh_index(exported['path'],args.binaries/'export-index',folder/'fresh-index')
                assert engine.encoded(current) == engine.encoded(restored.old['index'])
                partition = audit_partition(result,previous,current)
                transitions.append(dict(result=compact(result),partition=partition,
                    receipt_audit=restored.audit_current_acceptance(current),
                    exact_input=preserve_export(exported['path'],'edge-'+str(len(transitions))),
                    independent_kernel_acceptances=oracles(exported['path'],folder,0,all_kernels=False)))
                previous = current
            assert engine.encoded(previous) == engine.encoded(baseline_index)
            record('real-dependency-edge-fallback-refresh-and-restore',transitions=transitions)
        assert len(report['controls']) == len(REQUIRED_CONTROLS)
        assert {row['name'] for row in report['controls']} == set(REQUIRED_CONTROLS)
        report['passed'] = True
        write(out/'summary.json',report)
        print(json.dumps(dict(passed=True,controls=len(report['controls']),profile=report['profile'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workloads','producer','binaries','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    run(parser.parse_args())
