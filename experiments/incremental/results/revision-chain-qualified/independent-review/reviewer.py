#!/usr/bin/env python3
"""Independent, standard-library review of frozen revision lifecycle evidence.

No project modules are imported. Historical HMACs are format/content/linkage
checked; private-key validity remains an observed CI witness. Fresh kernel
execution is intentionally a separate operation over the enumerated inputs.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from artifacts import Artifacts, canonical, digest, hexid, loads, require
from economics import validate_economics
from reuse_rule import validate_index, validate_partition

SCHEMA = 'mathgraph.authenticated-revision-chain-lifecycle.v1'
SOURCES = ('IncrementalWorkload/Base.lean', 'IncrementalWorkload/Derived.lean',
           'IncrementalWorkload/Leaves.lean', 'Workload.lean', 'lakefile.toml', 'lean-toolchain')
SPARSE = 'mathgraph.incremental-lean.sparse-accepted.v1'
BASE = 'mathgraph.incremental-lean.v1'
CHAIN = 'mathgraph.lean-accepted-predecessor-chain.v1'
GENESIS = 'mathgraph.lean-source-owned-genesis.v1'
TRANSITION = 'mathgraph.lean-source-owned-transition.v1'
CAPTURE = 'mathgraph.lean-complete-source-capture.v1'
TOOLS = ('producer', 'checker', 'retained_checker', 'indexer', 'index_session', 'full_checker')
ROOTS = ['IncrementalWorkload.early', 'IncrementalWorkload.dependent', 'IncrementalWorkload.dependent_spec',
         'Std.HashMap.getElem?_insert', 'Std.HashMap.getElem?_erase', 'IncrementalWorkload.unrelated',
         'IncrementalWorkload.leaf', 'IncrementalWorkload.typed', 'IncrementalWorkload.typed_identity']


def equal(left, right, message):
    require(canonical(left) == canonical(right), message)


def source_bytes(repo, revision, path):
    return subprocess.check_output(['git', '-C', str(repo), 'show', revision + ':' + path])


def source_policy(repo, revision):
    paths = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '--name-only', revision], text=True).splitlines()
    selected = [p for p in paths if p in ('Cargo.toml', 'Cargo.lock', '.github/workflows/incremental-revision-chain.yml') or
                (p.startswith('src/') and p.endswith('.rs')) or
                (p.startswith('experiments/incremental/') and p.count('/') == 2 and p.endswith(('.py', '.lean', '.json')))]
    return {p:hashlib.sha256(source_bytes(repo, revision, p)).hexdigest() for p in selected}


def validate_structure(report, smoke):
    require(type(report) is dict and report.get('schema') == SCHEMA, 'unsupported lifecycle schema')
    for name in ('completed', 'correctness_passed', 'source_and_binary_stable'):
        require(report.get(name) is True, 'incomplete/failed lifecycle: ' + name)
    require(type(report.get('repetitions')) is int and report['repetitions'] > 0 and
            type(report.get('cycles')) is int and report['cycles'] > 0, 'positive integer actual sequence counts required')
    names = report.get('requested_profiles')
    require(type(names) is list and names and len(names) == len(set(names)) and
            set(names) <= {'original', 'expanded'} and set(report.get('profiles', {})) == set(names),
            'nonempty supported unique workload profiles required')
    if not smoke:
        require(report.get('qualified') is True and report.get('source_tracked_clean') is True and
                report['repetitions'] == 5 and report['cycles'] == 10 and set(names) == {'original','expanded'},
                'qualification requires clean exact source and both five-by-forty histories')


def config_for(path):
    return dict(export_file_path=path, use_stdin=False, permitted_axioms=['propext','Classical.choice','Quot.sound'],
                unpermitted_axiom_hard_error=True, num_threads=1, nat_extension=True, string_extension=True,
                print_success_message=True)


def patch_index(parent, patch):
    require(type(patch) is dict and set(patch) == {'schema','count','declarations','builtins'} and
            patch['schema'] == 'mathgraph.export-identity-baseline-patch.v1' and
            type(patch['count']) is int and patch['count'] == parent['count'], 'invalid predecessor index patch')
    current = copy.deepcopy(parent)
    require(type(patch['declarations']) is list and type(patch['builtins']) is dict, 'malformed index patch')
    last = -1
    for row in patch['declarations']:
        require(type(row) is dict and set(row) == set(parent['declarations'][0]) and
                type(row.get('index')) is int and last < row['index'] < parent['count'], 'bad sparse declaration position')
        pos = row['index']
        for key in ('key','name','kind','deps','index'):
            equal(row[key], parent['declarations'][pos][key], 'sparse patch changed declaration topology')
        require(hexid(row['own']) and hexid(row['closure']), 'invalid sparse declaration fingerprint')
        current['declarations'][pos] = row
        last = pos
    for name, value in patch['builtins'].items():
        require(name in parent['builtins'] and type(value) is list and len(value) == 2 and
                value[0] == parent['builtins'][name][0] and
                all(part is None or hexid(part) for part in value), 'invalid builtin patch')
        current['builtins'][name] = value
    return current


class Reviewer:
    def __init__(self, artifact, repo, source, smoke=False):
        require(re.fullmatch('[0-9a-f]{40}', source) is not None, 'explicit exact source SHA required')
        self.reviewer_paths=[Path(__file__).with_name(name) for name in
            ('reviewer.py','artifacts.py','controls.py','reuse_rule.py','economics.py')]
        self.reviewer_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.reviewer_paths}
        self.store = Artifacts(artifact)
        self.report = self.store.json(self.store.summary_member)
        validate_structure(self.report, smoke)
        self.repo, self.source, self.smoke = Path(repo).resolve(), source, smoke
        self.source_hashes = source_policy(self.repo, source)
        equal(self.report['source_sha256'], self.source_hashes, 'recorded source bytes differ from git show exact source')
        if not smoke:
            require(self.report['source_sha'] == source, 'qualified run names a different source commit')
        self.pins = loads(source_bytes(self.repo, source, 'experiments/incremental/pins.json'))
        self.expanded = loads(source_bytes(self.repo, source, 'experiments/incremental/delta-pins.json'))
        self.index_cache = {}
        self.inputs = {}
        self.actual_inputs = set()
        self.pairs = self.revisions = self.signed_objects = self.decisions = 0
        self.descriptor_checks = 0
        self.validate_binaries()
        observations=self.store.join(self.store.artifact,'ci-observations.json')
        self.ci_publisher_observed=False
        if observations in self.store.members:
            ci=self.store.json(observations)
            require(ci.get('source_sha')==source and ci.get('correctness_passed') is True and
                    ci.get('failures')==[],'CI publisher reports a failed/incomplete exact-source qualification')
            self.ci_publisher_observed=True
        require(smoke or self.ci_publisher_observed,'full qualification requires complete exact-source CI observations')

    def validate_binaries(self):
        records = self.report['binary_sha256']
        expected = set(TOOLS) | {p+':'+n for p in self.report['profiles'] for n in ('lean','leanchecker','leanchecker-paranoid')}
        require(set(records) == expected, 'missing/unexpected measured binary slots')
        for name, record in records.items():
            require(type(record) is dict and type(record.get('path')) is str and hexid(record.get('sha256')), 'invalid executable record')
            if ':' in name:
                require(record['sha256'] == self.pins['lean_release_binaries_sha256'][name.split(':')[1]], 'unpinned Lean release executable')
        before = self.store.join(self.store.artifact, 'binaries-before.sha256')
        after = self.store.join(self.store.artifact, 'binaries-after.sha256')
        self.binary_stability_manifest = before in self.store.members and after in self.store.members
        if self.binary_stability_manifest:
            equal(self.store.read(before).decode(), self.store.read(after).decode(), 'before/after executable manifest differs')
            lines = []
            for line in self.store.read(before).decode().splitlines():
                identity, path = line.split('  ',1)
                require(hexid(identity), 'bad executable manifest digest')
                lines.append((identity,path))
            for name, record in records.items():
                matches = [h for h,p in lines if record['path'] == p or record['path'].endswith('/'+p) or p.endswith('/'+record['path'])]
                require(matches and set(matches) == {record['sha256']}, 'measured binary absent/different in stable CI manifest: '+name)
        require(self.smoke or self.binary_stability_manifest, 'missing stable before/after CI executable manifests')
        for kind in ('source',):
            before=self.store.join(self.store.artifact,kind+'-before.sha256');after=self.store.join(self.store.artifact,kind+'-after.sha256')
            if before in self.store.members and after in self.store.members:
                equal(self.store.read(before).decode(),self.store.read(after).decode(),'before/after source manifest differs')
                for line in self.store.read(before).decode().splitlines():
                    identity,path=line.split('  ',1)
                    require(hashlib.sha256(source_bytes(self.repo,self.source,path)).hexdigest()==identity,'CI tracked source differs from git show: '+path)
            else:require(self.smoke,'missing before/after CI source manifests')

    def blob(self, record, role=None):
        member = self.store.archive(record)
        identity = record['uncompressed_sha256']
        if role is not None:
            key = (identity,record['uncompressed_bytes'])
            item = self.inputs.setdefault(key,dict(sha256=identity,bytes=key[1],member=member,encoding='gzip',
                compressed_member_sha256=record['sha256'],compressed_member_bytes=record['bytes'],roles=[],
                expected_returncode=0,profile=role.split(':')[0],observations=[]))
            if role not in item['roles']:item['roles'].append(role)
        return member

    def object_raw(self, session, category, identity, suffix='.json'):
        require(hexid(identity),'invalid signed object address')
        raw=self.store.saved_member(self.store.join(self.store.lifecycle,session,category,identity+suffix))
        require(hashlib.sha256(raw).hexdigest()==identity,'object content-address mismatch: '+category)
        return raw

    def signed(self, session, category, identity, schema):
        envelope=loads(self.object_raw(session,category,identity))
        require(type(envelope) is dict and set(envelope)=={'payload','hmac_sha256'} and
                hexid(envelope['hmac_sha256']) and type(envelope['payload']) is dict and
                envelope['payload'].get('schema')==schema,'invalid signed object envelope/domain')
        self.signed_objects+=1
        return envelope['payload']

    def process_outputs(self, process, returncode=0):
        require(type(process) is dict and process.get('returncode')==returncode and process.get('timed_out') is False,'failed/timed-out actual process')
        for kind in ('stdout','stderr'):
            raw=self.store.saved(process[kind+'_path'])
            require(hashlib.sha256(raw).hexdigest()==process[kind+'_sha256'],'actual process output SHA mismatch')

    def kernel(self, process, snapshot, tool):
        self.process_outputs(process)
        require(process['input_sha256']==snapshot['sha256'] and process['input_bytes']==snapshot['bytes'],'kernel input differs from accepted snapshot')
        require(process['command'][0]==self.report['binary_sha256'][tool]['path'],'kernel executable differs')
        raw=self.store.saved(process['config_path'])
        require(hashlib.sha256(raw).hexdigest()==process['config_sha256'],'kernel config SHA mismatch')
        equal(loads(raw),config_for(snapshot['path']),'kernel config differs from exact accepted snapshot')
        expected=[process['command'][0],'--from-export',snapshot['path']] if '--from-export' in process['command'] else [process['command'][0],process['config_path']]
        equal(process['command'],expected,'kernel invocation differs from declared actual input')

    def index(self, process, snapshot=None):
        self.process_outputs(process)
        identity=process['stdout_sha256']
        if identity not in self.index_cache:
            value=loads(self.store.saved(process['stdout_path']))
            validate_index(value)
            self.index_cache[identity]=value
        value=self.index_cache[identity]
        if snapshot is not None:
            require(process['input_sha256']==snapshot['sha256'] and process['input_bytes']==snapshot['bytes'],'index input differs from accepted snapshot')
            command=process['command']
            require(command[0]==self.report['binary_sha256']['indexer']['path'] and len(command)==2,'unexpected native index invocation')
            equal(loads(self.store.saved(command[1])),config_for(snapshot['path']),'native index configuration differs')
        return value

    def policy(self, value, profile):
        require(value['schema']=='mathgraph.source-owned-producer-policy.v1' and value['revision_mode']=='accepted-predecessor-v1','wrong producer chain policy')
        for name in ('producer','checker','retained_checker','indexer','index_session'):
            require(value['tools'][name]==self.report['binary_sha256'][name]['sha256'],'producer binary policy differs')
        for key,path in [('adapter_sha256','producer_delta.py'),('engine_sha256','engine.py'),('pins_sha256','pins.json'),('revision_adapter_sha256','revision_chain.py')]:
            require(value[key]==self.source_hashes['experiments/incremental/'+path],'producer source policy differs: '+key)
        require(value['profile']==('original-v1' if profile=='original' else self.expanded['profile']) and
                value['acceptance_receipt']==SPARSE and value['receipt_index_comparison']=='shared_json' and
                value['identity_index_wire']=='baseline_patch_v1' and value['identity_finish_mode']=='retained' and
                value['baseline_authority']=='source-owned-frozen-bytes-v1' and
                value['selected_kernel_backend']=='sha-pinned-retained-parser-v1' and
                value['source_policy']=='complete-six-file-capture;fixed-imports;accepted-predecessor-replacement-set', 'producer applicability policy differs')
        require(value['profile_policy_sha256']==(None if profile=='original' else self.source_hashes['experiments/incremental/delta-pins.json']) and
                value['representation']=='baseline-DAG;append-only-delta-DAG;original-declaration-schedule','producer profile/representation policy differs')
        roots=ROOTS if profile=='original' else loads(source_bytes(self.repo,self.source,'experiments/incremental/expanded-roots.json'))
        equal(value['roots'],roots,'producer root universe differs')

    def baseline_sources(self, profile):
        sources={}
        for name in SOURCES:
            raw=self.store.read(self.store.join(self.store.lifecycle,'sources',profile,'0',name))
            require(hashlib.sha256(raw).hexdigest()==self.pins['workload_sources_sha256'][name],'baseline source pin changed')
            sources[name]=raw.decode('utf-8')
        return sources

    def planned_step(self, sources, revision):
        state=(revision-1)%4
        if state in (0,2):
            name,before,after,decl='IncrementalWorkload/Base.lean','def early : Nat := 17','def early : Nat := 23','IncrementalWorkload.early'
        else:name,before,after,decl='IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5','IncrementalWorkload.unrelated'
        if state>=2:before,after=after,before
        require(sources[name].count(before)==1,'ambiguous predecessor source edit')
        target=dict(sources);target[name]=target[name].replace(before,after)
        return target,[name,before,after],[decl]

    def genesis(self, session, published, index, sources, profile):
        base=published['evidence_id'];head=published['head_id']
        record=self.signed(session+'/baseline-cache','records',base,BASE)
        equal(record['index'],index,'genesis full index differs from independently preserved index')
        require(record['status']=='VERIFIED' and record['export_sha256']==published['export_sha256'] and
                record['checked_indices']==list(range(index['count'])) and record['reused_indices']==[], 'genesis acceptance did not check every obligation')
        policy=record['provenance']
        require(policy['adapter_sha256']==self.source_hashes['experiments/incremental/engine.py'] and
                policy['checker_sha256']==self.report['binary_sha256']['checker']['sha256'] and
                policy['indexer_sha256']==self.report['binary_sha256']['indexer']['sha256'] and hexid(policy['issuer_key_sha256']), 'genesis verifier provenance differs')
        equal(policy['configuration'],dict(nat_extension=True,string_extension=True,num_threads=1,
            permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True),'genesis verifier assumptions differ')
        require(policy['policy']=='default','genesis verifier policy differs')
        state=self.store.json(self.store.join(self.store.lifecycle,session,'session-state.json'))
        require(state['base_evidence_id']==base and state['genesis_id']==head,'session genesis pointers differ')
        genesis=self.signed(session+'/cache','genesis',head,GENESIS)
        require(genesis['base_evidence_id']==base and genesis['source_root']==digest(sources) and genesis['export_sha256']==published['export_sha256'],'genesis source/export linkage differs')
        self.policy(genesis['provenance'],profile)
        return record

    def link(self,result,parent_head,parent_evidence,revision):
        require(result['status']=='VERIFIED' and hexid(result['evidence_id']) and result['previous_evidence']==parent_evidence,'revision did not establish immediate accepted parent')
        link=result['revision_chain']
        require(type(link['revision']) is int and link['revision']==revision and link['parent_head']==parent_head and link['parent_evidence']==parent_evidence and hexid(link['head_id']) and hexid(link['source_capture_id']),'chain link skipped/substituted predecessor')
        return link

    def receipt(self,session,result,parent,current,parent_head,parent_evidence,parent_export,revision,sources,profile):
        link=self.link(result,parent_head,parent_evidence,revision)
        policy=result['producer_provenance'];self.policy(policy,profile)
        receipt=self.signed(session+'/cache','records',result['evidence_id'],SPARSE)
        require(receipt['status']=='VERIFIED' and receipt['previous_evidence']==parent_evidence and receipt['export_sha256']==result['export_sha256'] and receipt['obligation_count']==current['count'],'receipt identity or predecessor differs')
        equal(patch_index(parent,receipt['index_patch']),current,'sparse receipt differs from complete independent index')
        equal(receipt['producer_provenance'],policy,'receipt producer provenance differs')
        rep=loads(self.object_raw(session+'/cache','representations',receipt['delta_representation']))
        require(rep['schema']=='mathgraph.lean-delta-representation.v1' and rep['base_evidence_id']==parent_evidence and rep['export_sha256']==result['export_sha256'],'representation parent/export differs')
        delta=self.object_raw(session+'/cache','deltas',rep['delta_sha256'],'.ndjson')
        transition=self.signed(session+'/cache','transitions',rep['transition_id'],TRANSITION)
        target,patch,names=self.planned_step(sources,revision)
        require(transition['base_evidence_id']==parent_evidence and transition['base_export_sha256']==parent_export and
                transition['baseline_source_root']==digest(sources) and transition['source_root']==digest(target) and transition['delta_sha256']==rep['delta_sha256'] and transition['changed_names']==names,'transition source/parent/delta mismatch')
        equal(transition['provenance'],policy,'transition executable/source policy differs')
        require(transition['producer_report']['revision']==revision and sorted(transition['producer_report']['changed_names'])==names and transition['producer_report']['stats']['compared_local_constants']==7 and transition['producer_report']['stats']['imported_identity_retained'] is True,'producer did not compare complete predecessor environment')
        head=self.signed(session+'/cache','chain',link['head_id'],CHAIN)
        expected=dict(schema=CHAIN,previous_head=parent_head,previous_evidence=parent_evidence,evidence_id=result['evidence_id'],revision=revision,source_capture_id=link['source_capture_id'],source_root=digest(target),export_sha256=result['export_sha256'],delta_sha256=rep['delta_sha256'],policy_sha256=digest(policy))
        equal(head,expected,'signed lifecycle head linkage differs')
        capture=loads(self.object_raw(session+'/cache','source-captures',link['source_capture_id']))
        equal(capture,dict(schema=CAPTURE,sources=target,patch=patch,claimed_names=names),'complete captured source/patch/name witness differs')
        audit=result.get('receipt_audit')
        if audit:
            for flag in ('issuer_hmac_valid','all_content_addresses_valid','head_hmac_valid','complete_source_capture_exact'):
                require(audit.get(flag) is True,'missing observed CI issuer audit witness')
        return target,receipt

    def run(self):
        report=self.report;expected_revisions=4*report['cycles']
        self.store.descriptors_in(report)
        for profile,observations in report['profiles'].items():
            require(set(observations['references'])=={'0','1','2','3'},'four complete source-state references required')
            refs={}
            for state,record in observations['references'].items():
                native=self.index(record['native_process']);python=self.index(record['python_process'])
                equal(native,python,'complete native/Python index differs')
                require(digest(native)==record['index_sha256'] and record['python_native_exact'] is True,'complete reference index fingerprint differs')
                refs[int(state)]=native
            require(len(observations['pairs'])==report['repetitions'],'missing actual lifetime pairs')
            baseline=self.baseline_sources(profile)
            for number,pair in enumerate(observations['pairs']):
                require(pair['repetition']==number and pair['completed'] is True and pair['correctness_passed'] is True and pair['accepted_revisions']==expected_revisions and len(pair['steps'])==expected_revisions,'incomplete continuing history')
                session='profiles/'+profile+'/pair-'+str(number)+'/session'
                genesis=pair['genesis'];self.blob(genesis['baseline_witness'],profile+':accepted-genesis')
                pin=self.pins['export_sha256']['baseline'] if profile=='original' else self.expanded['export_sha256']['baseline']
                require(genesis['export_sha256']==pin and genesis['baseline_witness']['uncompressed_sha256']==pin,'unpinned genesis input')
                snap=dict(sha256=pin,bytes=genesis['baseline_witness']['uncompressed_bytes'],path=genesis['baseline_export_path'])
                self.actual_inputs.add((pin,snap['bytes']));self.kernel(genesis['direct_rust'],snap,'full_checker')
                self.inputs[(pin,snap['bytes'])]['observations'].append(dict(profile=profile,pair=number,revision=0,
                    summary_member=self.store.summary_member,arm='interleaved and continuous genesis'))
                base=self.genesis(session,genesis,refs[0],baseline,profile)
                parent_head,parent_evidence=genesis['head_id'],genesis['evidence_id']
                previous,sources=refs[0],baseline
                for revision,step in enumerate(pair['steps'],1):
                    state=[1,2,3,0][(revision-1)%4]
                    require(step['revision']==revision and step['state']==state and step['cycle']==(revision-1)//4,'revision source-state order differs')
                    raw=self.store.archive_json(step['result_witness']);snapshot=step['snapshot']
                    require(raw['export_sha256']==snapshot['sha256'] and raw['evidence_id']==step['evidence_id'] and raw['previous_evidence']==parent_evidence and snapshot['seals']==snapshot['required_seals']==15,'raw accepted result/export/seals differs')
                    equal(raw['revision_chain'],step['revision_chain'],'raw result/head differs')
                    equal(raw['provenance'],base['provenance'],'verifier provenance changed inside chain')
                    self.kernel(step['direct_rust'],snapshot,'full_checker')
                    current=self.index(step['full_index_process'],snapshot)
                    equal(current,refs[state],'actual complete index differs from independent source reference')
                    require(step['full_index_sha256']==digest(current) and step['full_index_exact'] is True,'actual index fingerprint differs')
                    partition=validate_partition(raw,previous,current,parent_evidence,parent_provenance=base['provenance'])
                    for key in ('checked_indices','reused_indices','actual_kernel_checked','actual_kernel_total','independently_replayed_reused'):
                        equal(partition[key],step['partition_audit'][key],'independent selected partition differs: '+key)
                    self.decisions+=len(raw['decisions'])
                    parent_export=pin if revision==1 else pair['steps'][revision-2]['snapshot']['sha256']
                    sources,receipt=self.receipt(session,raw,previous,current,parent_head,parent_evidence,parent_export,revision,sources,profile)
                    equal(receipt['checked_indices'],partition['checked_indices'],'receipt selected set differs from independently coded predicate')
                    require(step['source_root']==digest(sources),'published source root differs')
                    audit=step['receipt_audit']
                    for flag in ('issuer_hmac_valid','all_content_addresses_valid','full_index_and_partition_exact','head_hmac_valid','complete_source_capture_exact'):
                        require(audit.get(flag) is True,'missing observed private-key receipt audit')
                    self.actual_inputs.add((snapshot['sha256'],snapshot['bytes']))
                    if step.get('export_witness'):
                        self.blob(step['export_witness'],profile+':accepted-revision')
                        require((step['export_witness']['uncompressed_sha256'],step['export_witness']['uncompressed_bytes'])==(snapshot['sha256'],snapshot['bytes']),'complete export witness differs')
                    if (snapshot['sha256'],snapshot['bytes']) in self.inputs:
                        self.inputs[(snapshot['sha256'],snapshot['bytes'])]['observations'].append(dict(profile=profile,pair=number,
                            revision=revision,summary_member=self.store.summary_member,arm='interleaved and continuous accepted',
                            evidence_id=raw['evidence_id'],parent_evidence=parent_evidence,
                            selected_indices=partition['checked_indices'],total_declarations=current['count'],
                            result_witness_member=self.store.join(self.store.lifecycle,step['result_witness']['artifact_relative_path'])))
                    if number==0 and revision<=4:
                        for tool in ('leanchecker','leanchecker-paranoid'):
                            self.kernel(step['representative_cpp'][tool],snapshot,profile+':'+tool)
                        equal(self.index(step['representative_cpp']['python_index']),current,'representative full Python index differs')
                    parent_head,parent_evidence=raw['revision_chain']['head_id'],raw['evidence_id'];previous=current
                    self.revisions+=1
                require(pair['final_head']==parent_head and pair['final_evidence']==parent_evidence and pair['final_export_sha256']==pair['steps'][-1]['snapshot']['sha256'],'final accepted head differs')
                equal(sources,baseline,'complete source cycle did not restore pinned source')
                equal(previous,refs[0],'semantic index did not restore genesis identity')
                if number==0:
                    cold=pair['cold_replay']
                    require(cold['passed'] is True and cold['expected_head']==parent_head and cold['actual_head']==parent_head and cold['replayed_revisions']==expected_revisions and cold['snapshot']['sha256']==pair['final_export_sha256'],'cold accepted history replay incomplete')
                    require(cold['ready']['current_head']==parent_head and cold['ready']['current_evidence']==parent_evidence and cold['ready']['revision']==expected_revisions,'cold state did not restore exact current evidence')
                self.continuous(profile,number,pair,refs,baseline)
                self.pairs+=1
        require(self.actual_inputs<=set(self.inputs),'missing complete actual accepted input coverage')
        economics=validate_economics(report)
        from controls import validate_controls
        controls=validate_controls(self.store,self.repo,self.source,smoke=self.smoke)
        for item in controls.get('negative_inputs',[]):
            key=(item['sha256'],item['bytes'])
            require(key not in self.inputs or self.inputs[key]['expected_returncode']==item['expected_returncode'],'conflicting expected outcomes for exact same input')
            self.inputs.setdefault(key,item)
        artifact_sha256=None
        if self.store.zip:
            with self.store.path.open('rb') as stream:
                artifact_sha256=hashlib.file_digest(stream,'sha256').hexdigest()
        summary_sha256=self.store.stream_hash(self.store.summary_member)[0]
        self.store.assert_stable()
        require(self.reviewer_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.reviewer_paths},
                'independent reviewer source changed during review')
        return dict(status='PASS_SMOKE_UNQUALIFIED' if self.smoke else 'PASS_INDEPENDENT_EXACT_ARTIFACT_REVIEW',
                    qualified=not self.smoke,expected_source=self.source,reported_source=report['source_sha'],
                    artifact_zip_sha256=artifact_sha256,artifact_summary_sha256=summary_sha256,
                    reported_source_tracked_clean=report['source_tracked_clean'],source_bytes_match_expected_commit=True,
                    profiles=list(report['profiles']),paired_lifetimes=self.pairs,accepted_revisions=self.revisions,
                    independently_checked_decisions=self.decisions,signed_object_links_checked=self.signed_objects,
                    compressed_archives_checked=self.store.archive_checks,historical_hmac_reauthenticated=False,
                    stable_ci_binary_manifest_checked=self.binary_stability_manifest,
                    complete_ci_publisher_observed=self.ci_publisher_observed,
                    reviewer_files_sha256=self.reviewer_hashes,
                    issuer_hmac_scope='Observed private-key CI audit flags; this public reviewer checks object addresses, domains, source/policy/parent links only.',
                    input_fingerprint_scope='Complete raw native/Python full-index witnesses and independent SCC/selection replay; declaration own-hash/export bridge remains the frozen tool witness.',
                    fresh_kernels_rerun_here=False,economics=economics,controls=controls,
                    complete_inputs=sorted(self.inputs.values(),key=lambda x:x['sha256']))

    def continuous(self,profile,number,pair,refs,baseline):
        continuous=pair['continuous']
        require(continuous['completed'] is True and continuous['order']==(['candidate','direct'] if number%2==0 else ['direct','candidate']),'continuous arm order is missing/nonalternating')
        raw=self.store.saved(continuous['summary_path'])
        require(hashlib.sha256(raw).hexdigest()==continuous['summary_sha256'],'continuous raw summary SHA differs')
        equal(loads(raw),{k:v for k,v in continuous.items() if k not in ('summary_path','summary_sha256')},'continuous raw summary differs')
        candidate,direct=continuous['candidate'],continuous['direct'];genesis=candidate['genesis']
        n=len(pair['steps'])
        require(candidate['completed'] is True and direct['completed'] is True and len(candidate['steps'])==n and len(direct['commands'])==n+1,'continuous history lacks actual candidate/direct commands')
        require(genesis['revision']==0 and genesis['export_sha256']==pair['genesis']['export_sha256'] and genesis['source_root']==digest(baseline),'continuous genesis differs')
        session='profiles/'+profile+'/pair-'+str(number)+'/continuous/candidate/session'
        self.genesis(session,genesis,refs[0],baseline,profile)
        parent_head,parent_evidence=genesis['head_id'],genesis['evidence_id'];previous,sources=refs[0],baseline
        for revision,(actual,expected) in enumerate(zip(candidate['steps'],pair['steps']),1):
            current=refs[expected['state']];partition=expected['partition_audit']
            expected_count=dict(total=current['count'],scheduled=len(partition['checked_indices']),rechecked=len(partition['checked_indices']),reused=len(partition['reused_indices']),invalidated=len(partition['checked_indices']))
            equal(actual['counts'],expected_count,'continuous counts differ from independently audited selected partition')
            require(actual['export_sha256']==expected['snapshot']['sha256'] and actual['snapshot_bytes']==expected['snapshot']['bytes'] and actual['source_root']==expected['source_root'],'continuous accepted input differs from independent arm')
            native=actual['native_kernel_report']
            require(native['status']=='checked' and native['code']==0 and native['chain_mode'] is True and native['revision']==revision and
                    native['checked']==expected_count['rechecked'] and native['total_declarations']==current['count'] and
                    native['kernel']=='sokonanoda_real_selected_declaration_check' and
                    native['scope']=='selected_obligations_under_caller_trusted_environment','continuous actual native checks differ')
            equal(loads(actual['checker_result']['stdout']),dict(checked=expected_count['rechecked'],
                total_declarations=current['count'],scope='selected_obligations_under_caller_trusted_environment'),'continuous selected checker stdout differs')
            require(actual['checker_result']['code']==0 and actual['checker_result']['stderr']=='','continuous selected checker outcome differs')
            parent_export=genesis['export_sha256'] if revision==1 else candidate['steps'][revision-2]['export_sha256']
            sources,receipt=self.receipt(session,actual,previous,current,parent_head,parent_evidence,parent_export,revision,sources,profile)
            equal(receipt['checked_indices'],partition['checked_indices'],'continuous receipt selected set differs')
            require(actual['full_index_exact'] is True and actual['independent_full_index_sha256']==digest(current),'continuous independent index identity differs')
            parent_head,parent_evidence=actual['revision_chain']['head_id'],actual['evidence_id'];previous=current
        require(candidate['final_head']==parent_head and candidate['final_evidence']==parent_evidence,'continuous final head differs')
        expected=[(pair['genesis']['export_sha256'],pair['genesis']['baseline_witness']['uncompressed_bytes'])]+[(s['snapshot']['sha256'],s['snapshot']['bytes']) for s in pair['steps']]
        for revision,(command,(identity,size)) in enumerate(zip(direct['commands'],expected)):
            snapshot=command['snapshot']
            require(command['revision']==revision and snapshot['sha256']==identity and snapshot['bytes']==size and snapshot['seals']==snapshot['required_seals']==15,'continuous direct input order/identity differs')
            self.kernel(command,snapshot,'full_checker')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=Reviewer(args.artifact,args.repo,args.source,args.smoke).run()
    except Exception as error:
        result=dict(status='FAIL_CLOSED',qualified=False,error=type(error).__name__+': '+str(error),expected_source=args.source)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        (args.output.parent/'inputs.json').write_text(json.dumps(dict(status='FAIL_CLOSED',qualified=False,
            expected_source=args.source,artifact=str(args.artifact),inputs=[]),indent=2)+'\n')
        print(json.dumps(result),file=sys.stderr)
        raise SystemExit(1)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    inputs_path=args.output.parent/'inputs.json'
    inputs_path.write_text(json.dumps(dict(status=result['status'],expected_source=args.source,reported_source=result['reported_source'],
        qualified=result['qualified'],historical_hmac_reauthenticated=False,artifact=str(args.artifact),
        artifact_zip_sha256=result['artifact_zip_sha256'],artifact_summary_sha256=result['artifact_summary_sha256'],
        inputs=result['complete_inputs']),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='complete_inputs'},separators=(',',':')))


if __name__=='__main__':main()
