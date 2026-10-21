#!/usr/bin/env python3
"""Authenticated accepted-predecessor continuation over the existing delta adapter.

The caller retains the expected head outside the cache. A valid historical
prefix alone is never evidence that it is the latest revision. Cold recovery
replays the complete accepted source history, including genuine selected checks.
This bounded prototype still materializes and hashes the whole export per step.
"""
import json
from pathlib import Path
import time

import engine
from producer_delta import (DeltaSession, GENESIS, SOURCES, SPARSE_ACCEPTANCE,
                            TRANSITION, _same_index_json, authenticate,
                            authenticate_sparse_acceptance, seal, sha)

CHAIN = 'mathgraph.lean-accepted-predecessor-chain.v1'
CAPTURE = 'mathgraph.lean-complete-source-capture.v1'


class RevisionChainSession(DeltaSession):
    def __init__(self, *args, **kwargs):
        for field in ('sparse_index_wire', 'sparse_receipt', 'frozen_baseline', 'revision_chain'):
            if field in kwargs and kwargs[field] is not True:
                raise ValueError('revision chain requires ' + field)
            kwargs[field] = True
        super().__init__(*args, **kwargs)
        self.delta_provenance['revision_adapter_sha256'] = sha(Path(__file__).read_bytes())
        self.revision = 0
        self.head_id = None
        self.poisoned = False
        self.pending = False
        self.started = False

    def _poison(self):
        self.poisoned = True
        self.used = True
        # Keep only the sealed actual input for independent rejection replay.
        # It is never reusable state; close() disposes it after the audit.
        for process in (self.producer, self.index, self.kernel_process):
            if process is not None:
                process.close()

    def start(self, expected_head=None):
        tick, cpu = time.perf_counter(), self.cpu_time()
        try:
            if self.started or self.poisoned:
                raise ValueError('chain session cannot be restarted in place')
            if (self.root / 'session-state.json').exists() and expected_head is None:
                raise ValueError('cold chain requires caller expected head; cache is not a latestness authority')
            report = super().start()
            state = json.loads((self.root / 'session-state.json').read_bytes(), object_pairs_hook=engine.strict_object)
            self.genesis_head = state['genesis_id']
            self.head_id = self.genesis_head
            self.started = True
            entries = self._history(expected_head) if expected_head is not None else []
            for wanted_head, entry in entries:
                capture_raw = self._object('source-captures', entry['source_capture_id'], '.json')
                capture = json.loads(capture_raw, object_pairs_hook=engine.strict_object)
                self._validate_capture(capture)
                if engine.digest(capture['sources']) != entry['source_root']:
                    raise ValueError('cold chain source root mismatch')
                source_dir = self.temp / 'cold-source'
                for name, text in capture['sources'].items():
                    path = source_dir / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text)
                # Reconstruct producer exporter history, never issue a delta
                # directly from an unauthenticated changed-name hint.
                transaction = self.prepare(source_dir, capture['patch'], capture['claimed_names'])
                payload = authenticate(transaction['attestation'], self.key, TRANSITION)
                if payload['delta_sha256'] != entry['delta_sha256']:
                    raise ValueError('cold producer delta history mismatch')
                # Authenticate *all* old objects before replay can persist them;
                # immutable_write must never silently repair authority records.
                stored = self._audit_entry(entry)
                representation = json.loads(self._object('representations', stored['delta_representation'], '.json'),
                                            object_pairs_hook=engine.strict_object)
                original = json.loads(self._object('transitions', representation['transition_id'], '.json'),
                                      object_pairs_hook=engine.strict_object)
                original_payload = authenticate(original, self.key, TRANSITION)
                # Timing samples and private output paths are observational and
                # nondeterministic. Keep the exact historical envelope after
                # reproducing its authenticated semantic inputs and delta bytes.
                if ({k:v for k,v in original_payload.items() if k != 'producer_report'} !=
                        {k:v for k,v in payload.items() if k != 'producer_report'} or
                        original_payload['producer_report'].get('revision') != transaction['producer_report'].get('revision')):
                    raise ValueError('cold regenerated transition applicability mismatch')
                transaction['attestation'] = original
                transaction['producer_report'] = original_payload['producer_report']
                result = self.validate_apply(transaction)
                if result['status'] != 'VERIFIED' or self.head_id != wanted_head:
                    raise ValueError('cold accepted predecessor replay mismatch')
            if expected_head is not None and self.head_id != expected_head:
                raise ValueError('cold chain expected head mismatch')
            report = dict(report, baseline_start_seconds=report['wall_seconds'],
                          replayed_revisions=len(entries), current_head=self.head_id,
                          current_evidence=self.base_id, revision=self.revision,
                          latestness_scope='caller_supplied_expected_head;no_external_monotonic_service',
                          wall_seconds=time.perf_counter()-tick, cpu_seconds=self.cpu_time()-cpu)
            self.start_report = report
            return report
        except Exception:
            self._poison()
            raise

    def _history(self, expected_head):
        history, seen, head = [], set(), expected_head
        while head != self.genesis_head:
            if head in seen or len(seen) >= 10000:
                raise ValueError('cyclic or oversized accepted history')
            seen.add(head)
            raw = self._object('chain', head, '.json')
            entry = authenticate(json.loads(raw, object_pairs_hook=engine.strict_object), self.key, CHAIN)
            required = {'schema','previous_head','previous_evidence','evidence_id','revision',
                        'source_capture_id','source_root','export_sha256','delta_sha256','policy_sha256'}
            if set(entry) != required or type(entry['revision']) is not int or entry['revision'] < 1:
                raise ValueError('unsupported accepted chain entry')
            if entry['policy_sha256'] != engine.digest(self.delta_provenance):
                raise ValueError('accepted chain toolchain/policy mismatch')
            history.append((head, entry))
            head = entry['previous_head']
        history.reverse()
        parent_head, parent_evidence = self.genesis_head, self.base_id
        for revision, (head, entry) in enumerate(history, 1):
            if (entry['revision'] != revision or entry['previous_head'] != parent_head or
                    entry['previous_evidence'] != parent_evidence):
                raise ValueError('accepted predecessor linkage mismatch')
            parent_head, parent_evidence = head, entry['evidence_id']
        return history

    @staticmethod
    def _validate_capture(capture):
        if (type(capture) is not dict or set(capture) != {'schema','sources','patch','claimed_names'} or
                capture['schema'] != CAPTURE or type(capture['sources']) is not dict or
                set(capture['sources']) != set(SOURCES) or
                any(type(v) is not str or len(v.encode()) > 1000000 for v in capture['sources'].values()) or
                type(capture['claimed_names']) is not list or
                any(type(v) is not str for v in capture['claimed_names'])):
            raise ValueError('invalid complete accepted source capture')
        patch = capture['patch']
        if patch is not None and (type(patch) not in (list,tuple) or len(patch) != 3 or
                                  any(type(v) is not str for v in patch)):
            raise ValueError('invalid accepted source patch')

    def prepare(self, source_dir, patch, claimed_names):
        try:
            if not self.started or self.poisoned or self.pending:
                raise ValueError('chain requires one pending transition from its accepted head')
            transaction = super().prepare(source_dir, patch, claimed_names)
            self._prepared_capture_sha256 = engine.digest(transaction['source_capture'])
            self.pending = True
            return transaction
        except Exception:
            self._poison()
            raise

    def _accepted(self, evidence_id, parent, parent_id):
        raw = self._object('records', evidence_id, '.json')
        envelope = json.loads(raw, object_pairs_hook=engine.strict_object)
        domain = envelope.get('payload', {}).get('schema') if type(envelope) is dict else None
        if domain == SPARSE_ACCEPTANCE:
            record = authenticate_sparse_acceptance(raw, evidence_id, self.key, parent)
            record['provenance'] = parent['provenance']
        else:
            record = engine.authenticate_record(raw, evidence_id, self.key)
        if (record.get('previous_evidence') != parent_id or
                record.get('producer_provenance') != self.delta_provenance or
                record.get('provenance') != parent['provenance']):
            raise ValueError('accepted receipt predecessor/provenance mismatch')
        return record

    def _audit_entry(self, entry, parent=None, parent_id=None, source_root=None):
        parent = self.old if parent is None else parent
        parent_id = self.base_id if parent_id is None else parent_id
        source_root = self.source_root if source_root is None else source_root
        record = self._accepted(entry['evidence_id'], parent, parent_id)
        representation = json.loads(self._object('representations', record['delta_representation'], '.json'),
                                    object_pairs_hook=engine.strict_object)
        delta = self._object('deltas', representation['delta_sha256'], '.ndjson')
        transition = authenticate(json.loads(self._object('transitions', representation['transition_id'], '.json'),
                                             object_pairs_hook=engine.strict_object), self.key, TRANSITION)
        if (record['export_sha256'] != entry['export_sha256'] or
                representation.get('schema') != 'mathgraph.lean-delta-representation.v1' or
                representation['base_evidence_id'] != parent_id or
                representation['export_sha256'] != entry['export_sha256'] or
                sha(delta) != entry['delta_sha256'] or
                transition['delta_sha256'] != entry['delta_sha256'] or
                transition['base_evidence_id'] != parent_id or
                transition['base_export_sha256'] != parent['export_sha256'] or
                transition['baseline_source_root'] != source_root or
                transition['source_root'] != entry['source_root'] or
                transition['provenance'] != self.delta_provenance):
            raise ValueError('persisted accepted transition linkage mismatch')
        return record

    def validate_apply(self, transaction):
        tick, cpu = time.perf_counter(), self.cpu_time()
        try:
            if self.poisoned or not self.started or not self.pending:
                raise ValueError('chain requires a live prepared predecessor transition')
            if engine.digest(transaction['source_capture']) != self._prepared_capture_sha256:
                raise ValueError('prepared complete source capture was modified')
            capture = dict(transaction['source_capture'], schema=CAPTURE)
            if capture['patch'] is not None:
                capture['patch'] = list(capture['patch'])
            self._validate_capture(capture)
            payload = authenticate(transaction['attestation'], self.key, TRANSITION)
            if (engine.digest(capture['sources']) != payload['source_root'] or
                    sorted(capture['claimed_names']) != payload['changed_names']):
                raise ValueError('source capture differs from authenticated transition')
            parent, parent_id, parent_head = self.old, self.base_id, self.head_id
            result = super().validate_apply(transaction)
            if result['status'] != 'VERIFIED':
                self._poison()
                return result
            persist_tick, persist_cpu = time.perf_counter(), self.cpu_time()
            record = self._accepted(result['evidence_id'], parent, parent_id)
            if record['export_sha256'] != result['export_sha256']:
                raise ValueError('live receipt export mismatch')
            # Capture uses the already sealed bytes that the fresh oracle also
            # receives. Layout was derived while writing those exact bytes,
            # rather than JSON-parsing the full export again.
            admitted_bytes = Path(self.snapshot_path).read_bytes()
            if len(admitted_bytes) != result['representation']['export_bytes']:
                raise ValueError('sealed successor snapshot length mismatch')
            capture_id = self._put('source-captures', engine.encoded(capture), '.json')
            entry = dict(schema=CHAIN, previous_head=parent_head, previous_evidence=parent_id,
                         evidence_id=result['evidence_id'], revision=self.revision+1,
                         source_capture_id=capture_id, source_root=payload['source_root'],
                         export_sha256=result['export_sha256'], delta_sha256=payload['delta_sha256'],
                         policy_sha256=engine.digest(self.delta_provenance))
            head = self._put('chain', engine.encoded(seal(entry, self.key)), '.json')
            # Promote only after genuine selected acceptance and all durable
            # objects. Any earlier exception closes all speculative processes.
            self.last_parent_record, self.last_parent_evidence_id = parent, parent_id
            self.last_parent_source_root = self.source_root
            self.last_accepted_record = record
            self.old, self.base_id = record, result['evidence_id']
            self.baseline_sources, self.source_root = dict(capture['sources']), payload['source_root']
            self.frozen_baseline_bytes, self.frozen_baseline_sha256 = admitted_bytes, result['export_sha256']
            self.layout = self._materialized_layout
            self.head_id, self.revision = head, self.revision+1
            self.used, self.pending = False, False
            result['revision_chain'] = dict(head_id=head, revision=self.revision,
                                           parent_head=parent_head, parent_evidence=parent_id,
                                           source_capture_id=capture_id)
            extra = time.perf_counter()-persist_tick
            result['timings']['chain_promotion_seconds'] = extra
            result['timings']['chain_promotion_cpu_seconds'] = self.cpu_time()-persist_cpu
            result['timings']['persistence_seconds'] += extra
            result['timings']['persistence_cpu_seconds'] += result['timings']['chain_promotion_cpu_seconds']
            result['timings']['consumer_seconds'] = time.perf_counter()-tick
            result['timings']['consumer_cpu_seconds'] = self.cpu_time()-cpu
            result['timings']['end_to_end_seconds'] = transaction.get('prepare_wall_seconds',0) + result['timings']['consumer_seconds']
            result['timings']['end_to_end_cpu_seconds'] = transaction.get('prepare_cpu_seconds',0) + result['timings']['consumer_cpu_seconds']
            self.result = result
            return result
        except Exception:
            self._poison()
            raise

    def audit_current_acceptance(self, index):
        if self.revision < 1 or self.poisoned:
            raise ValueError('no live accepted chain step to audit')
        record = self._accepted(self.base_id, self.last_parent_record, self.last_parent_evidence_id)
        if not _same_index_json(record['index'], index):
            raise ValueError('accepted predecessor index differs from independent index')
        entry = authenticate(json.loads(self._object('chain', self.head_id, '.json'),
                                        object_pairs_hook=engine.strict_object), self.key, CHAIN)
        if (entry['evidence_id'] != self.base_id or entry['revision'] != self.revision or
                entry['previous_evidence'] != self.last_parent_evidence_id or
                entry['policy_sha256'] != engine.digest(self.delta_provenance)):
            raise ValueError('live accepted head linkage mismatch')
        capture = json.loads(self._object('source-captures', entry['source_capture_id'], '.json'),
                             object_pairs_hook=engine.strict_object)
        self._validate_capture(capture)
        if engine.digest(capture['sources']) != entry['source_root']:
            raise ValueError('live accepted source root mismatch')
        self._audit_entry(entry, self.last_parent_record, self.last_parent_evidence_id,
                          self.last_parent_source_root)
        return dict(issuer_hmac_valid=True, all_content_addresses_valid=True,
                    parent_evidence=self.last_parent_evidence_id, evidence_id=self.base_id,
                    head_id=self.head_id, revision=self.revision,
                    scope='current step receipt/head/capture/representation/delta/transition and admitted parent binding; kernel checked separately')

    def apply(self, source_dir, patch, claimed_names):
        tick, cpu = time.perf_counter(), self.cpu_time()
        try:
            result = self.validate_apply(self.prepare(source_dir, patch, claimed_names))
        except (ValueError, KeyError, OSError, TypeError) as error:
            self._poison()
            result = dict(status='UNKNOWN', evidence_id=None, reason=str(error), counts=None,
                          decisions=[], action_authorization='NONE', poisoned=True)
        result.setdefault('timings', {})['end_to_end_seconds'] = time.perf_counter()-tick
        result['timings']['end_to_end_cpu_seconds'] = self.cpu_time()-cpu
        return result
