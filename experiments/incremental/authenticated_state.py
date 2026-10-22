#!/usr/bin/env python3
"""Authenticated delta-state identity, separate from a materialized export SHA.

Acceptance uses the existing source owner, typed index, reuse predicate and
genuine retained Rust kernel. A state ID addresses a deterministic construction
from verified genesis and authenticated deltas; it is never a file hash or a
claim of semantic equivalence. Full NDJSON export is an explicit O(N) operation.
"""
from dataclasses import dataclass, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
from types import MappingProxyType

import engine
from producer_delta import (DeltaSession, authenticate, reconstruct_index_patch,
                            seal, sha, _same_index_json)
from revision_chain import RevisionChainSession

STATE_TRANSITION = 'mathgraph.lean-source-owned-state-transition.v1'
STATE_ACCEPTANCE = 'mathgraph.incremental-lean.state-accepted.v1'
STATE_REPRESENTATION = 'mathgraph.lean-authenticated-export-state.v1'
STATE_GENESIS = 'mathgraph.lean-authenticated-export-state-genesis.v1'
STATE_CHAIN = 'mathgraph.lean-accepted-state-chain.v1'
STATE_RESULT = 'mathgraph.incremental-lean.state-result.v1'


def _hexid(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


@dataclass(frozen=True)
class _Names:
    additions: object
    parent: object = None

    def get(self, index):
        here = self
        while here is not None:
            if index in here.additions:
                return here.additions[index]
            here = here.parent
        raise KeyError(index)

    def contains(self, index):
        try:
            self.get(index)
            return True
        except KeyError:
            return False


@dataclass(frozen=True)
class ExportRecipe:
    """Immutable serialization recipe, not acceptance authority.

    The baseline is admitted by the session's real full kernel check. Warm
    composition visits only delta rows and the bounded local replacement map;
    it never reads baseline slices or copies the complete names/declaration DAG.
    Name lookup and explicit export may depend on accepted history length.
    """
    baseline: bytes
    dag_spans: tuple
    declarations: tuple
    slots: object
    names: _Names
    replacements: object
    byte_count: int
    parent: object = None
    appended_dag: bytes = b''

    @classmethod
    def from_baseline(cls, raw, layout=None):
        if type(raw) is not bytes:
            raise ValueError('immutable baseline bytes required')
        layout = DeltaSession._layout(raw) if layout is None else layout
        declarations = tuple(layout['declarations'])
        slots = {name:(kind, length) for name,kind,_start,length in declarations if name is not None}
        return cls(raw, tuple(layout['dags']), declarations, MappingProxyType(slots),
                   _Names(MappingProxyType(layout['names'])), MappingProxyType({}), len(raw))

    def append(self, delta, changed_names):
        if type(delta) is not bytes or type(changed_names) is not list or (
                any(type(n) is not str for n in changed_names) or len(set(changed_names)) != len(changed_names)):
            raise ValueError('exact delta bytes and unique replacement names required')
        if delta and not delta.endswith(b'\n'):
            raise ValueError('delta rows must preserve NDJSON newline framing')
        additions, replacements, dags = {}, {}, []
        def name_at(index):
            return additions[index] if index in additions else self.names.get(index)
        for raw in delta.splitlines(keepends=True):
            row = json.loads(raw, object_pairs_hook=engine.strict_object)
            if type(row) is not dict or any(k in row for k in ('meta','inductive','quot')):
                raise ValueError('unsupported global/schedule transition')
            if 'in' in row:
                index = row['in']
                if type(index) is not int or index < 0 or index in additions or self.names.contains(index):
                    raise ValueError('attempted old or malformed name DAG mutation')
                part = row.get('str', row.get('num'))
                if type(part) is not dict or type(part.get('pre')) is not int:
                    raise ValueError('malformed name DAG row')
                prefix = name_at(part['pre'])
                additions[index] = (prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
            kinds = set(row) & engine.SIMPLE
            if kinds:
                if len(kinds) != 1 or len(row) != 1:
                    raise ValueError('ambiguous declaration delta')
                kind = next(iter(kinds));name = name_at(row[kind]['name'])
                if name in replacements:
                    raise ValueError('duplicate declaration replacement')
                if name not in self.slots or self.slots[name][0] != kind:
                    raise ValueError('new declaration, kind or schedule change')
                replacements[name] = raw
            else:
                dags.append(raw)
        if set(replacements) != set(changed_names):
            raise ValueError('declared changes differ from export mutations')
        current = dict(self.replacements)  # Only the bounded source-local slots.
        size = self.byte_count
        for name, raw in replacements.items():
            old_length = len(current[name]) if name in current else self.slots[name][1]
            size += len(raw)-old_length
            current[name] = raw
        appended = b''.join(dags)
        return replace(self, names=_Names(MappingProxyType(additions),self.names),
                       replacements=MappingProxyType(current), byte_count=size+len(appended),
                       parent=self, appended_dag=appended)

    def iter_chunks(self):
        if self.parent is None:
            yield self.baseline
            return
        view = memoryview(self.baseline)
        for start,length in self.dag_spans:
            yield view[start:start+length]
        layers,here = [],self
        while here.parent is not None:
            layers.append(here.appended_dag);here=here.parent
        yield from reversed(layers)
        for name,_kind,start,length in self.declarations:
            yield self.replacements[name] if name in self.replacements else view[start:start+length]


def authenticate_state_acceptance(raw, evidence_id, key, baseline, expected_parent_state):
    """Authenticate a state receipt and apply the unchanged reuse predicate.

    `baseline` and expected parent state must already be issuer-authenticated.
    This function never checks a proof or promotes an unverified cache entry.
    """
    if not _hexid(evidence_id) or sha(raw) != evidence_id:
        raise ValueError('state receipt content-address mismatch')
    value = authenticate(json.loads(raw,object_pairs_hook=engine.strict_object),key,STATE_ACCEPTANCE)
    required = {'schema','status','state_id','parent_state_id','previous_evidence',
                'producer_provenance','identity','obligation_count','checked_indices'}
    if set(value) != required or value['status'] != 'VERIFIED':
        raise ValueError('unsupported state acceptance certificate')
    if any(not _hexid(value[k]) for k in ('state_id','parent_state_id','previous_evidence')):
        raise ValueError('malformed state acceptance reference')
    if not _hexid(expected_parent_state) or value['parent_state_id'] != expected_parent_state:
        raise ValueError('state receipt parent mismatch')
    if type(baseline) is not dict or baseline.get('status') != 'VERIFIED':
        raise ValueError('state receipt requires issuer-authenticated verified baseline')
    if (not isinstance(baseline.get('provenance'),dict) or
            not isinstance(value['producer_provenance'],dict)):
        raise ValueError('missing state acceptance provenance')
    identity = value['identity']
    if type(identity) is not dict or set(identity) != {'wire','value'}:
        raise ValueError('ambiguous state typed-index witness')
    if identity['wire'] == 'baseline_patch_v1':
        index = reconstruct_index_patch(baseline['index'],identity['value'])
    elif identity['wire'] == 'full_index_v1':
        index = identity['value']
    else:
        raise ValueError('unsupported state typed-index witness')
    if (type(index) is not dict or type(index.get('count')) is not int or
            type(value['obligation_count']) is not int or
            value['obligation_count'] != index['count'] or
            type(index.get('declarations')) is not list or len(index['declarations']) != index['count']):
        raise ValueError('state receipt count mismatch')
    selected = value['checked_indices']
    if (type(selected) is not list or any(type(i) is not int or i < 0 or i >= index['count'] for i in selected)
            or selected != sorted(set(selected))):
        raise ValueError('invalid state checked-obligation list')
    expected,_ = engine.reuse_decisions(baseline,index,baseline['provenance'],value['previous_evidence'])
    if selected != expected:
        raise ValueError('state receipt disagrees with verified applicability rule')
    checked = set(selected)
    return dict(value,index=index,provenance=baseline['provenance'],
                reused_indices=[i for i in range(index['count']) if i not in checked])


class StateChainSession(RevisionChainSession):
    transition_schema = STATE_TRANSITION
    chain_schema = STATE_CHAIN
    chain_subject = 'state_id'
    result_schema = STATE_RESULT

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.delta_provenance.update(state_adapter_sha256=sha(Path(__file__).read_bytes()),
            representation_authority=STATE_REPRESENTATION, acceptance_receipt=STATE_ACCEPTANCE,
            baseline_authority='source-owned-authenticated-delta-state-v1')
        self.recipe = None
        self._state_id = None
        self._proposed_recipe = None
        self._proposed_state_id = None
        self._attempt_identity = None

    @property
    def state_id(self):
        return self._state_id

    def _initialize_chain_representation(self):
        self.recipe = ExportRecipe.from_baseline(self.frozen_baseline_bytes,self.layout)
        self.genesis_evidence_id = self.base_id
        genesis = dict(schema=STATE_GENESIS,genesis_id=self.genesis_head,
                       genesis_evidence_id=self.base_id,export_sha256=self.export_pins['baseline'],
                       policy_sha256=engine.digest(self.delta_provenance))
        self.genesis_state_id = self._put('representations',engine.encoded(genesis),'.json')
        self._state_id = self.genesis_state_id

    def _parent_state(self,parent,parent_id):
        if 'state_id' in parent:
            if not _hexid(parent['state_id']):raise ValueError('malformed authenticated parent state')
            return parent['state_id']
        if (parent_id != self.genesis_evidence_id or
                parent.get('export_sha256') != self.export_pins['baseline']):
            raise ValueError('unrecognized full-export genesis parent')
        return self.genesis_state_id

    def _transition_reference(self):
        return dict(base_state_id=self.state_id)

    def _accepted_representation_id(self,record):
        return record['state_id']

    def prepare(self,*args,**kwargs):
        # A previous explicit export is never the current attempted input.
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.snapshot_path = None
        self._proposed_recipe = self._proposed_state_id = self._attempt_identity = None
        return super().prepare(*args,**kwargs)

    def _validated_update_baseline(self):
        if (self.recipe is None or self.old.get('status') != 'VERIFIED' or
                self._parent_state(self.old,self.base_id) != self.state_id):
            raise ValueError('missing authenticated immutable parent state')
        return self.recipe

    def _materialize(self,baseline,delta,changed_names):
        # Preserve the old materializer's delta-only admission guards. The
        # native typed index and genuine kernel independently parse these rows.
        self._proposed_recipe = baseline.append(delta,changed_names)
        self._proposed_state_id = None
        self._attempt_identity = dict(parent_state_id=self.state_id,delta_sha256=sha(delta))
        return None,self._proposed_recipe.byte_count

    def _selected_config(self):
        if self.kernel_process is None:
            raise ValueError('authenticated state requires genuine retained kernel')
        return None

    def _result_identity(self,status,export_hash):
        if export_hash is not None:
            raise ValueError('state path unexpectedly acquired a full export hash')
        return dict(state_id=self._proposed_state_id if status=='VERIFIED' else None,
                    export_sha256=None)

    def _representation_report(self,delta,export_bytes):
        return dict(kind=STATE_REPRESENTATION,delta_bytes=len(delta),export_bytes=export_bytes,
                    full_export_disk_bytes_written=0,immutable_memfd=False,
                    full_export_bytes_materialized=0,full_export_bytes_hashed=0,
                    full_successor_bytes_read=0)

    def _persist_verified_acceptance(self,transaction,delta,payload,index,update,selected,decisions,export_hash):
        if export_hash is not None or self._proposed_recipe is None:
            raise ValueError('unprepared authenticated state')
        delta_id = self._put('deltas',delta,'.ndjson')
        transition_id = self._put('transitions',engine.encoded(transaction['attestation']),'.json')
        representation = dict(schema=STATE_REPRESENTATION,genesis_id=self.genesis_head,
            genesis_export_sha256=self.export_pins['baseline'],parent_state_id=self.state_id,
            parent_evidence_id=self.base_id,delta_sha256=delta_id,transition_id=transition_id,
            source_root=payload['source_root'],policy_sha256=engine.digest(self.delta_provenance),
            revision=self.revision+1,export_bytes=self._proposed_recipe.byte_count)
        state_id = self._put('representations',engine.encoded(representation),'.json')
        wire = update.get('index_wire')
        if wire == 'baseline_patch_v1':
            identity = dict(wire=wire,value=update['index_patch'])
        elif wire == 'full_index_v1':
            identity = dict(wire=wire,value=index)
        else:
            raise ValueError('unknown state identity witness')
        accepted = dict(schema=STATE_ACCEPTANCE,status='VERIFIED',state_id=state_id,
            parent_state_id=self.state_id,previous_evidence=self.base_id,
            producer_provenance=self.delta_provenance,identity=identity,
            obligation_count=index['count'],checked_indices=selected)
        candidate = engine.encoded(seal(accepted,self.key))
        restored = authenticate_state_acceptance(candidate,sha(candidate),self.key,self.old,self.state_id)
        if not _same_index_json(restored['index'],index):
            raise ValueError('signed state receipt does not reconstruct live typed index')
        receipt_id = self._put('records',candidate,'.json')
        self._proposed_state_id = state_id
        for decision in decisions:
            if decision['status']=='VERIFIED_NEW':decision['evidence_id']=receipt_id
        return receipt_id

    def _accepted(self,evidence_id,parent,parent_id):
        raw = self._object('records',evidence_id,'.json')
        record = authenticate_state_acceptance(raw,evidence_id,self.key,parent,self._parent_state(parent,parent_id))
        if (record['previous_evidence'] != parent_id or
                record['producer_provenance'] != self.delta_provenance or
                record['provenance'] != parent['provenance']):
            raise ValueError('accepted state predecessor/provenance mismatch')
        return record

    def _audit_entry(self,entry,parent=None,parent_id=None,source_root=None):
        parent = self.old if parent is None else parent
        parent_id = self.base_id if parent_id is None else parent_id
        source_root = self.source_root if source_root is None else source_root
        record = self._accepted(entry['evidence_id'],parent,parent_id)
        representation = json.loads(self._object('representations',record['state_id'],'.json'),
                                    object_pairs_hook=engine.strict_object)
        required = {'schema','genesis_id','genesis_export_sha256','parent_state_id','parent_evidence_id',
                    'delta_sha256','transition_id','source_root','policy_sha256','revision','export_bytes'}
        if set(representation) != required:
            raise ValueError('unsupported persisted state representation')
        delta = self._object('deltas',representation['delta_sha256'],'.ndjson')
        transition = authenticate(json.loads(self._object('transitions',representation['transition_id'],'.json'),
                                             object_pairs_hook=engine.strict_object),self.key,STATE_TRANSITION)
        if (representation['schema'] != STATE_REPRESENTATION or record['state_id'] != entry['state_id'] or
                representation['genesis_id'] != self.genesis_head or
                representation['genesis_export_sha256'] != self.export_pins['baseline'] or
                representation['parent_state_id'] != self._parent_state(parent,parent_id) or
                representation['parent_evidence_id'] != parent_id or
                representation['source_root'] != entry['source_root'] or
                representation['revision'] != entry['revision'] or
                type(representation['export_bytes']) is not int or representation['export_bytes'] < 0 or
                representation['policy_sha256'] != engine.digest(self.delta_provenance) or
                sha(delta) != entry['delta_sha256'] or
                transition['delta_sha256'] != entry['delta_sha256'] or
                transition['base_evidence_id'] != parent_id or
                transition['base_state_id'] != self._parent_state(parent,parent_id) or
                transition['baseline_source_root'] != source_root or
                transition['source_root'] != entry['source_root'] or
                transition['provenance'] != self.delta_provenance):
            raise ValueError('persisted authenticated state linkage mismatch')
        return record

    def _prepare_chain_promotion(self,result):
        if (self._proposed_recipe is None or not _hexid(self._proposed_state_id) or
                result['state_id'] != self._proposed_state_id or
                result['representation']['export_bytes'] != self._proposed_recipe.byte_count):
            raise ValueError('accepted state promotion mismatch')
        return self._proposed_recipe,self._proposed_state_id

    def _promote_chain_representation(self,prepared,result):
        self.recipe,self._state_id = prepared
        self._proposed_recipe = None
        self._proposed_state_id = None

    def materialize_current(self):
        """Explicit full export; does not retroactively change receipt identity."""
        if not self.started or self.poisoned or self.pending or self.recipe is None:
            raise ValueError('no live accepted state to export')
        return self._export_recipe(self.recipe,dict(state_id=self.state_id,
            scope='explicit_materialization_not_acceptance_or_reuse_authority'))

    def materialize_attempt(self):
        """Export staged candidate for an independent oracle; grants no warrant."""
        if self._proposed_recipe is None or self._attempt_identity is None:
            raise ValueError('no parsed attempted recipe to export')
        return self._export_recipe(self._proposed_recipe,dict(self._attempt_identity,
            state_id=None,scope='unaccepted_attempt_for_independent_oracle_only'))

    def _export_recipe(self,recipe,identity):
        tick,cpu = time.perf_counter(),self.cpu_time()
        if self.fd is not None:os.close(self.fd)
        self.fd = os.memfd_create('mathgraph-authenticated-state-export',os.MFD_ALLOW_SEALING)
        digest,count,buffer = hashlib.sha256(),0,bytearray()
        def write(raw):
            nonlocal count
            digest.update(raw);count+=len(raw);view=memoryview(raw)
            while view:
                n=os.write(self.fd,view);view=view[n:]
        for chunk in recipe.iter_chunks():
            if len(chunk) > 1024*1024:
                if buffer:write(buffer);buffer.clear()
                write(chunk)
            else:
                buffer.extend(chunk)
                if len(buffer)>=1024*1024:write(buffer);buffer.clear()
        if buffer:write(buffer)
        if count != recipe.byte_count:raise ValueError('materialized state byte count mismatch')
        seals=15
        fcntl.fcntl(self.fd,getattr(fcntl,'F_ADD_SEALS',1033),seals)
        if fcntl.fcntl(self.fd,getattr(fcntl,'F_GET_SEALS',1034)) & seals != seals:
            raise ValueError('state export could not be sealed')
        self.snapshot_path=f'/proc/{os.getpid()}/fd/{self.fd}'
        return dict(identity,path=self.snapshot_path,export_sha256=digest.hexdigest(),
                    export_bytes=count,seals=seals,wall_seconds=time.perf_counter()-tick,
                    cpu_seconds=self.cpu_time()-cpu)
