#!/usr/bin/env python3
"""Read-only public evidence replay using fresh full indexes and kernels.

This program imports no incremental engine, producer, receipt authenticator or
state implementation. Public HMAC envelopes are content-addressed historical
records, not reauthenticated issuer evidence: the secret deliberately is not
published. Their applicability is instead compared with independently rebuilt
full indexes and the actual exports are checked by fresh kernel processes.
"""
import argparse
import ast
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import statistics
import subprocess
import tempfile
import time

STATE_ACCEPTANCE='mathgraph.incremental-lean.state-accepted.v1'
STATE_REPRESENTATION='mathgraph.lean-authenticated-export-state.v1'
STATE_TRANSITION='mathgraph.lean-source-owned-state-transition.v1'
STATE_CHAIN='mathgraph.lean-accepted-state-chain.v1'
STATE_GENESIS='mathgraph.lean-authenticated-export-state-genesis.v1'
SIMPLE={'axiom','def','opaque','thm'}


def require(condition,reason):
    if not condition:raise ValueError(reason)


def hexid(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def git_sha(value):
    """Exact SHA-1 Git object ID used by this repository, not a SHA-256 CAS."""
    return type(value) is str and len(value)==40 and all(c in '0123456789abcdef' for c in value)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def strict_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate JSON field')
        result[key]=value
    return result


def decode(raw):return json.loads(raw,object_pairs_hook=strict_object)


def member(root,path):
    require(type(path) is str and path and not Path(path).is_absolute() and '..' not in Path(path).parts,
            'unsafe artifact member')
    root=Path(root).resolve();target=(root/path).resolve()
    require(target.is_relative_to(root),'artifact member escapes root')
    return target


def checked_bytes(root,path,identity=None,size=None):
    raw=member(root,path).read_bytes()
    if identity is not None:require(hexid(identity) and sha(raw)==identity,'artifact content address mismatch: '+path)
    if size is not None:require(type(size) is int and len(raw)==size,'artifact byte count mismatch: '+path)
    return raw


def public_envelope(value,schema):
    require(type(value) is dict and set(value)=={'payload','hmac_sha256'} and hexid(value['hmac_sha256']),
            'malformed historical issuer envelope')
    require(type(value['payload']) is dict and value['payload'].get('schema')==schema,
            'historical receipt domain mismatch')
    return value['payload']


def cas(session,category,identity,suffix='.json'):
    require(hexid(identity),'malformed content address')
    return checked_bytes(session,'cache/'+category+'/'+identity+suffix,identity)


def compose(baseline,delta,claimed_names):
    """Independent, intentionally O(N), whole-NDJSON serialization oracle."""
    require(type(baseline) is bytes and type(delta) is bytes,'exact export bytes required')
    require(not delta or delta.endswith(b'\n'),'delta lacks newline framing')
    require(type(claimed_names) is list and len(set(claimed_names))==len(claimed_names),'ambiguous changed names')
    names={0:''};dags=[];declarations=[];slots={}
    for raw in baseline.splitlines(keepends=True):
        row=decode(raw)
        require(type(row) is dict,'nonobject export row')
        if 'in' in row:
            part=row.get('str',row.get('num'));prefix=names[part['pre']]
            names[row['in']]=(prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
        kinds=set(row)&(SIMPLE|{'quot','inductive'})
        if kinds:
            require(len(kinds)==1,'ambiguous baseline declaration')
            kind=next(iter(kinds));name=None if kind=='inductive' else names[row[kind]['name']]
            declarations.append((name,kind,raw))
            if name is not None:slots[name]=kind
        else:dags.append(raw)
    replacements={}
    for raw in delta.splitlines(keepends=True):
        row=decode(raw)
        require(type(row) is dict and not (set(row)&{'meta','inductive','quot'}),'unsupported global delta')
        if 'in' in row:
            require(type(row['in']) is int and row['in'] not in names,'old name DAG mutation')
            part=row.get('str',row.get('num'));prefix=names[part['pre']]
            names[row['in']]=(prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
        kinds=set(row)&SIMPLE
        if kinds:
            require(len(kinds)==1 and len(row)==1,'ambiguous declaration replacement')
            kind=next(iter(kinds));name=names[row[kind]['name']]
            require(name in slots and slots[name]==kind and name not in replacements,'schedule/kind/repetition changed')
            replacements[name]=raw
        else:dags.append(raw)
    require(set(replacements)==set(claimed_names),'claimed changes differ from actual declarations')
    return b''.join(dags+[replacements.get(name,raw) for name,_kind,raw in declarations])


def partition(old,current):
    """Finite applicability calculation over fresh full indexes, not a kernel."""
    globals_same=all(old[key]==current[key] for key in ('meta','builtins','complex'))
    schedule_same=globals_same and old['schedule']==current['schedule']
    previous={row['key']:row for row in old['declarations']}
    prefix=True;checked=[];reused=[]
    for row in current['declarations']:
        past=previous.get(row['key'])
        prefix=bool(prefix and globals_same and past is not None and past['index']==row['index'] and past['own']==row['own'])
        local=bool(schedule_same and row['kind'] in SIMPLE and past is not None and
                   past['own']==row['own'] and past['closure']==row['closure'])
        (reused if prefix or local else checked).append(row['index'])
    return checked,reused


def index_witness(baseline,identity):
    require(type(identity) is dict and set(identity)=={'wire','value'},'invalid identity wire')
    if identity['wire']=='full_index_v1':return identity['value']
    require(identity['wire']=='baseline_patch_v1','unknown identity wire')
    patch=identity['value']
    require(set(patch)=={'schema','count','declarations','builtins'} and
            patch['schema']=='mathgraph.export-identity-baseline-patch.v1' and
            type(patch['count']) is int and patch['count']==baseline['count'],'bad index patch schema/count')
    rows=list(baseline['declarations']);builtins=dict(baseline['builtins']);previous=-1
    require(type(patch['declarations']) is list and type(patch['builtins']) is dict,'bad patch rows')
    for row in patch['declarations']:
        require(type(row) is dict and set(row)==set(rows[0]),'changed index row shape')
        pos=row.get('index');require(type(pos) is int and previous<pos<len(rows),'patch order or range')
        for key in ('index','key','name','kind','deps'):
            require(type(row[key]) is type(rows[pos][key]) and row[key]==rows[pos][key],'sparse topology mismatch')
        require(hexid(row['own']) and hexid(row['closure']),'malformed fingerprints')
        rows[pos]=row;previous=pos
    for name,value in patch['builtins'].items():
        require(name in builtins and type(value) is list and len(value)==2 and value[0]==builtins[name][0],
                'builtin patch mismatch')
        require(all(part is None or hexid(part) for part in value),'malformed builtin fingerprint')
        builtins[name]=value
    return dict(baseline,declarations=rows,builtins=builtins)


def economics(pairs,seed=20261016,bootstrap_repetitions=10000):
    require(type(pairs) is list and pairs,'no economic samples')
    update=[p['apply_wall_seconds'] for p in pairs];direct=[p['direct_wall_seconds'] for p in pairs]
    require(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in update+direct),'invalid measured duration')
    ratio=statistics.median(update)/statistics.median(direct);rng=random.Random(seed);ratios=[]
    for _ in range(bootstrap_repetitions):
        ids=[rng.randrange(len(pairs)) for _ in pairs]
        ratios.append(statistics.median(update[i] for i in ids)/statistics.median(direct[i] for i in ids))
    ratios.sort();interval=[ratios[int(q*(len(ratios)-1))] for q in (.025,.975)]
    wins=sum(a<b for a,b in zip(update,direct));passed=ratio<1 and wins>len(pairs)/2 and interval[1]<1
    return dict(passed=passed,status='SPEEDUP' if passed else 'NO_SPEEDUP',
        apply_median_wall_seconds=statistics.median(update),direct_median_wall_seconds=statistics.median(direct),
        median_ratio=ratio,paired_wins=wins,paired_count=len(pairs),bootstrap_ratio_interval_95=interval,
        bootstrap_repetitions=bootstrap_repetitions,bootstrap_seed=seed)


def configuration(export):
    return dict(export_file_path=str(export),use_stdin=False,permitted_axioms=['propext','Classical.choice','Quot.sound'],
        unpermitted_axiom_hard_error=True,num_threads=1,nat_extension=True,string_extension=True,print_success_message=True)


def process(command,out,timeout):
    out.mkdir(parents=True,exist_ok=False)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);tick=time.perf_counter()
    try:
        result=subprocess.run([str(a) for a in command],capture_output=True,timeout=timeout)
        code,stdout,stderr,timed_out=result.returncode,result.stdout,result.stderr,False
    except subprocess.TimeoutExpired as error:
        code,stdout,stderr,timed_out=None,error.stdout or b'',error.stderr or b'',True
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    (out/'stdout').write_bytes(stdout);(out/'stderr').write_bytes(stderr)
    return dict(command=[str(a) for a in command],returncode=code,timed_out=timed_out,
        wall_seconds=time.perf_counter()-tick,
        completed_child_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)),stdout


class Store:
    def __init__(self,root,summary):
        self.root=Path(root).resolve()
        self.historical_root=None
        self.archives_checked={}
        def walk(value):
            if type(value) is dict:
                if value.get('encoding')=='gzip' and 'artifact_relative_path' in value and 'path' in value:
                    absolute=Path(value['path']);relative=Path(value['artifact_relative_path'])
                    require(tuple(absolute.parts[-len(relative.parts):])==relative.parts,'archive path/root contradiction')
                    candidate=absolute
                    for _ in relative.parts:candidate=candidate.parent
                    if self.historical_root is None:self.historical_root=candidate
                    require(candidate==self.historical_root,'mixed historical evidence roots')
                for child in value.values():walk(child)
            elif type(value) is list:
                for child in value:walk(child)
        walk(summary)

    def relative(self,path):
        path=Path(path)
        if path.is_absolute():
            require(self.historical_root is not None and path.is_relative_to(self.historical_root),'historical path outside evidence')
            path=path.relative_to(self.historical_root)
        return str(path)

    def blob(self,descriptor):
        require(descriptor.get('encoding')=='gzip' and hexid(descriptor.get('sha256')) and
                hexid(descriptor.get('uncompressed_sha256')) and type(descriptor.get('bytes')) is int and
                type(descriptor.get('uncompressed_bytes')) is int,'invalid compressed descriptor')
        compressed=checked_bytes(self.root,descriptor['artifact_relative_path'],descriptor['sha256'],descriptor['bytes'])
        raw=gzip.decompress(compressed)
        require(sha(raw)==descriptor['uncompressed_sha256'] and len(raw)==descriptor['uncompressed_bytes'],
                'decompressed artifact identity mismatch')
        self.archives_checked[descriptor['artifact_relative_path']]=descriptor['sha256']
        return raw

    def read(self,path):
        relative=self.relative(path);target=member(self.root,relative)
        if target.is_file():return target.read_bytes()
        descriptor=decode(member(self.root,relative+'.archive.json').read_bytes())
        require(self.relative(descriptor['original_path'])==relative,'archive substitutes different original member')
        return self.blob(descriptor)

    def object(self,session,category,identity,suffix='.json'):
        require(hexid(identity),'malformed CAS identity')
        raw=self.read(str(Path(session)/'cache'/category/(identity+suffix)))
        require(sha(raw)==identity,'persisted object content address mismatch: '+category)
        return raw


def fresh_index(raw,args,folder):
    folder.mkdir(parents=True,exist_ok=True)
    export=folder/'input.ndjson';export.write_bytes(raw)
    config=folder/'config.json';config.write_bytes(canonical(configuration(export)))
    result,stdout=process([args.indexer,config],folder/'index-process',args.timeout)
    require(result['returncode']==0 and not result['timed_out'],'fresh full index failed')
    index=decode(stdout)
    require(set(index)=={'meta','declarations','count','builtins','complex','schedule'} and
            type(index['count']) is int and len(index['declarations'])==index['count'],'incomplete fresh typed index')
    require(sha(export.read_bytes())==sha(raw),'full-index input changed')
    export.unlink()
    return index,result


def run_kernels(raw,args,folder,expected,all_kernels):
    folder.mkdir(parents=True,exist_ok=True)
    export=folder/'input.ndjson';export.write_bytes(raw);export.chmod(0o444)
    config=folder/'config.json';config.write_bytes(canonical(configuration(export)))
    observations={}
    for name,binary in [('rust',args.rust)]+([('cpp',args.cpp),('paranoid',args.paranoid)] if all_kernels else []):
        command=[binary,config] if name=='rust' else [binary,'--from-export',export]
        result,_=process(command,folder/name,args.timeout)
        result.update(input_sha256=sha(raw),input_bytes=len(raw),expected_returncode=expected)
        observations[name]=result
        require(result['returncode']==expected and not result['timed_out'],
                'fresh independent kernel verdict disagreement: '+name+' '+sha(raw))
        require(sha(export.read_bytes())==sha(raw),'fresh kernel input changed')
    export.chmod(0o644);export.unlink()
    return observations


def validate_source_capture(capture,step,parent_sources):
    require(set(capture)=={'schema','sources','patch','claimed_names'} and
            capture['schema']=='mathgraph.lean-complete-source-capture.v1','source-capture shape mismatch')
    sources=capture['sources'];patch=capture['patch']
    require(type(sources) is dict and set(sources)==set(parent_sources) and
            all(type(k) is str and type(v) is str for k,v in sources.items()),'source universe mismatch')
    require(sha(canonical(sources))==step['source_root'] and patch==step['patch'] and
            capture['claimed_names']==step['claimed_names'],'source capture is not actual planned revision')
    expected=dict(parent_sources)
    if patch is not None:
        require(type(patch) is list and len(patch)==3 and all(type(x) is str for x in patch),'malformed source patch')
        name,before,after=patch
        require(name in expected and before and expected[name].count(before)==1,'ambiguous immediate-parent patch')
        expected[name]=expected[name].replace(before,after)
    require(expected==sources,'source modifications outside reported region')
    return sources


def audit_genesis(store,session,genesis,index,baseline_sha,policy_expected,source_root_expected):
    state=decode(store.read(str(Path(session)/'session-state.json')))
    require(state=={'base_evidence_id':genesis['evidence_id'],'genesis_id':genesis['head_id']},'genesis session-state mismatch')
    identity=genesis['evidence_id']
    raw=store.read(str(Path(session)/'baseline-cache'/'records'/(identity+'.json')))
    require(sha(raw)==identity,'baseline receipt content address mismatch')
    baseline=public_envelope(decode(raw),'mathgraph.incremental-lean.v1')
    require(baseline['status']=='VERIFIED' and baseline['export_sha256']==baseline_sha and
            baseline['index']==index,'baseline receipt differs from fresh full input index')
    authority=public_envelope(decode(store.object(session,'genesis',genesis['head_id'])),
                              'mathgraph.lean-source-owned-genesis.v1')
    require(set(authority)=={'schema','base_evidence_id','source_root','export_sha256','provenance'} and
            authority['base_evidence_id']==identity and authority['export_sha256']==baseline_sha and
            authority['source_root']==source_root_expected,
            'source-owned genesis binding mismatch')
    require(authority['provenance']==policy_expected,'genesis policy differs from update policy')
    if 'state_id' in genesis:
        value=decode(store.object(session,'representations',genesis['state_id']))
        require(value==dict(schema=STATE_GENESIS,genesis_id=genesis['head_id'],genesis_evidence_id=identity,
                           export_sha256=baseline_sha,policy_sha256=sha(canonical(authority['provenance']))),
                'state genesis construction/export separation mismatch')
    return authority


def audit_step(store,session,result,parent_index,current_index,step,parent_state,parent_head,
               parent_evidence,parent_sources,genesis,kind):
    link=result['revision_chain'];require(result['status']=='VERIFIED','unaccepted primary update')
    require(result['previous_evidence']==parent_evidence and link['parent_head']==parent_head and
            link['parent_evidence']==parent_evidence and link['revision']==step['revision'],
            'accepted predecessor chain skipped or substituted')
    receipt=public_envelope(decode(store.object(session,'records',result['evidence_id'])),
        STATE_ACCEPTANCE if kind=='state' else 'mathgraph.incremental-lean.sparse-accepted.v1')
    require(receipt['status']=='VERIFIED' and receipt['previous_evidence']==parent_evidence and
            receipt['producer_provenance']==result['producer_provenance'],'receipt predecessor/policy differs')
    identity=receipt['identity'] if kind=='state' else dict(wire='baseline_patch_v1',value=receipt['index_patch'])
    rebuilt=index_witness(parent_index,identity)
    selected,reused=partition(parent_index,current_index)
    require(rebuilt==current_index and receipt['obligation_count']==current_index['count'] and
            receipt['checked_indices']==selected,'receipt identity/applicability differs from fresh full index')
    total=current_index['count'];expected_counts=dict(total=total,scheduled=len(selected),rechecked=len(selected),
        reused=len(reused),invalidated=len(selected))
    require(result['counts']==expected_counts,'claimed work counts differ from independently selected set')
    native=result['native_kernel_report']
    require(native['status']=='checked' and native['code']==0 and native['checked']==len(selected) and
            native['total_declarations']==total and native['kernel']=='sokonanoda_real_selected_declaration_check',
            'retained kernel report disagrees with independently selected work')
    if 'decisions' in result:
        decisions=result['decisions'];require(len(decisions)==total,'incomplete decision witness')
        selected_set=set(selected)
        for d,row in zip(decisions,current_index['declarations']):
            require(d['name']==row['name'] and d['index']==row['index'] and
                    d['dependency_witness']==dict(own=row['own'],closure=row['closure'],direct=row['deps']) and
                    d['status']==('VERIFIED_NEW' if row['index'] in selected_set else 'VERIFIED_REUSED'),
                    'declaration decision witness mismatch')
    if kind=='state':
        require(set(receipt)=={'schema','status','state_id','parent_state_id','previous_evidence',
            'producer_provenance','identity','obligation_count','checked_indices'},'ambiguous state acceptance')
        require(result.get('export_sha256') is None and receipt['state_id']==result['state_id'] and
            receipt['parent_state_id']==parent_state and result['state_id']!=step['export_sha256'],
            'state ID masquerades as exact-export SHA or wrong parent')
        representation=decode(store.object(session,'representations',result['state_id']))
        require(set(representation)=={'schema','genesis_id','genesis_export_sha256','parent_state_id',
            'parent_evidence_id','delta_sha256','transition_id','source_root','policy_sha256','revision','export_bytes'},
            'ambiguous state construction')
        require(representation['schema']==STATE_REPRESENTATION and representation['genesis_id']==genesis['head_id'] and
            representation['genesis_export_sha256']==genesis['export_sha256'] and
            representation['parent_state_id']==parent_state and representation['parent_evidence_id']==parent_evidence and
            representation['source_root']==step['source_root'] and representation['revision']==step['revision'] and
            representation['export_bytes']==step['export_bytes'] and
            representation['policy_sha256']==sha(canonical(result['producer_provenance'])),
            'state construction does not bind actual accepted input')
        require(all(result['representation'].get(key)==0 for key in ('full_export_bytes_materialized',
            'full_export_bytes_hashed','full_successor_bytes_read','full_export_disk_bytes_written')),
            'state report claims full-export work in supposedly sparse arm')
        domain=STATE_TRANSITION;subject='state_id';head_domain=STATE_CHAIN
        base_name='base_state_id';base_value=parent_state
    else:
        require(receipt['export_sha256']==result['export_sha256']==step['export_sha256'],
                'legacy exact input mismatch')
        representation=decode(store.object(session,'representations',receipt['delta_representation']))
        require(representation['schema']=='mathgraph.lean-delta-representation.v1' and
            representation['base_evidence_id']==parent_evidence and representation['export_sha256']==step['export_sha256'],
            'legacy representation mismatch')
        domain='mathgraph.lean-source-owned-transition.v1';subject='export_sha256'
        head_domain='mathgraph.lean-accepted-predecessor-chain.v1';base_name='base_export_sha256';base_value=parent_state
    transition=public_envelope(decode(store.object(session,'transitions',representation['transition_id'])),domain)
    delta=store.object(session,'deltas',representation['delta_sha256'],'.ndjson')
    require(transition['delta_sha256']==sha(delta)==step['delta_sha256'] and
            transition['base_evidence_id']==parent_evidence and transition[base_name]==base_value and
            transition['baseline_source_root']==sha(canonical(parent_sources)) and transition['source_root']==step['source_root'] and
            transition['changed_names']==sorted(step['claimed_names']) and transition['provenance']==result['producer_provenance'],
            'source transition does not bind exact delta/parent/source/policy')
    head=public_envelope(decode(store.object(session,'chain',link['head_id'])),head_domain)
    require(set(head)=={'schema','previous_head','previous_evidence','evidence_id','revision','source_capture_id',
            'source_root',subject,'delta_sha256','policy_sha256'} and head['previous_head']==parent_head and
            head['previous_evidence']==parent_evidence and head['evidence_id']==result['evidence_id'] and
            head['revision']==step['revision'] and head['source_capture_id']==link['source_capture_id'] and
            head['source_root']==step['source_root'] and head[subject]==result[subject] and
            head['delta_sha256']==sha(delta) and head['policy_sha256']==sha(canonical(result['producer_provenance'])),
            'accepted head chain mismatch')
    capture=decode(store.object(session,'source-captures',link['source_capture_id']))
    sources=validate_source_capture(capture,step,parent_sources)
    return dict(delta=delta,sources=sources,checked=len(selected),reused=len(reused),
        state_id=result.get('state_id'),evidence_id=result['evidence_id'],head_id=link['head_id'],
        index_sha256=sha(canonical(current_index)))


def audit_process(store,record,expected,input_sha,*,expected_binary,snapshot,cpp=False):
    require(type(record) is dict and record.get('returncode')==expected and record.get('timed_out') is False,
            'missing, failed or unsupported historical oracle')
    for kind in ('stdout','stderr'):
        raw=store.read(record[kind+'_path'])
        require(sha(raw)==record[kind+'_sha256'],'historical oracle output identity mismatch')
    require(record['input_sha256']==input_sha and record['input_bytes']==snapshot['bytes'] and
            snapshot['sha256']==input_sha and type(snapshot['bytes']) is int and snapshot['bytes']>0,
            'oracle checked a different input or length')
    require(type(snapshot.get('seals')) is int and snapshot['seals'] & 15 == 15,
            'changed-input comparator lacks immutable sealed snapshot')
    config_raw=store.read(record['config_path'])
    require(sha(config_raw)==record['config_sha256'],'historical oracle configuration identity mismatch')
    require(decode(config_raw)==configuration(snapshot['path']),'historical oracle configuration changed policy/input')
    expected_command=([str(expected_binary),'--from-export',snapshot['path']] if cpp else
                      [str(expected_binary),record['config_path']])
    require(record['command']==expected_command,'historical measured command is not the pinned checker/input')


def audit_reference(store,record,index,expected_indexer):
    native,python=record['native_process'],record['python_process']
    for observed in (native,python):
        require(observed['returncode']==0 and observed['timed_out'] is False,'reference parser failed or unsupported')
        for name in ('stdout','stderr'):
            require(sha(store.read(observed[name+'_path']))==observed[name+'_sha256'],'reference process output changed')
    native_index=decode(store.read(native['stdout_path']));python_index=decode(store.read(python['stdout_path']))
    require(native_index==python_index==index and record['python_native_exact'] is True and
            sha(canonical(index))==record['index_sha256'],'independent Python/native full indexes differ')
    require(native['command'][0]==expected_indexer and len(native['command'])==2,'reference native command mismatch')
    config=decode(store.read(native['command'][1]))
    require(config==configuration(config['export_file_path']),'reference native verifier policy mismatch')
    expected_script=('import json,sys; from pathlib import Path; import engine; '
        'print(json.dumps(engine.make_index(Path(sys.argv[1])), '
        'sort_keys=True,separators=(",",":"),ensure_ascii=True))')
    require(len(python['command'])==4 and python['command'][1:3]==['-c',expected_script] and
            python['command'][3]==config['export_file_path'],'reference Python command/input mismatch')


def source_set(store,profile,state):
    paths=('IncrementalWorkload/Base.lean','IncrementalWorkload/Derived.lean','IncrementalWorkload/Leaves.lean',
           'Workload.lean','lakefile.toml','lean-toolchain')
    return {name:store.read('sources/'+profile+'/'+str(state)+'/'+name).decode() for name in paths}


def source_inventory(repo):
    here=repo/'experiments/incremental'
    paths={Path('Cargo.toml'),Path('Cargo.lock'),Path('.github/workflows/incremental-revision-chain.yml')}
    paths.update(path.relative_to(repo) for path in (repo/'src').rglob('*.rs'))
    for pattern in ('*.py','*.lean','*.json'):
        paths.update(path.relative_to(repo) for path in here.glob(pattern))
    paths.update(path.relative_to(repo) for path in (repo/'.github/workflows').glob('*incremental*.yml'))
    return {str(path) for path in paths if (repo/path).is_file()}


def audit_source_manifest(repo,manifest):
    require(type(manifest) is dict and set(manifest)==source_inventory(repo),'qualified source manifest omits or adds runtime files')
    for path,identity in manifest.items():
        require(sha(member(repo,path).read_bytes())==identity,'qualified source manifest mismatch: '+path)


def audit_policy(policy,summary,kind):
    sources=summary['source_sha256']
    mapping={'adapter_sha256':'producer_delta.py','engine_sha256':'engine.py',
             'revision_adapter_sha256':'revision_chain.py','pins_sha256':'pins.json'}
    if kind=='state':mapping['state_adapter_sha256']='authenticated_state.py'
    for field,path in mapping.items():
        require(policy[field]==sources['experiments/incremental/'+path],'issuer policy source differs from exact measured source')
    for name,identity in policy['tools'].items():
        require(name in summary['binary_sha256'] and identity==summary['binary_sha256'][name]['sha256'],
                'issuer tool policy differs from frozen measured executables')
    require(set(policy['tools'])=={'producer','checker','indexer','index_session','retained_checker'},
            'issuer tool universe differs')
    if policy['profile']!='original-v1':
        require(policy['profile_policy_sha256']==sources['experiments/incremental/delta-pins.json'],'expanded profile policy mismatch')


def audit_historical_tool_pins(summary,pins):
    native={'producer':'delta-producer','checker':'check-selected',
        'retained_checker':'check-selected-retained-session','indexer':'export-index',
        'index_session':'index-session','full_checker':'sokonanoda'}
    expected=dict(native)
    for profile in summary['profiles']:
        for name in ('lean','leanchecker','leanchecker-paranoid'):expected[profile+':'+name]=name
    records=summary['binary_sha256']
    require(type(records) is dict and set(records)==set(expected),'historical executable inventory mismatch')
    for role,name in expected.items():
        record=records[role]
        require(type(record) is dict and set(record)=={'path','sha256'} and
                type(record['path']) is str and Path(record['path']).name==name and hexid(record['sha256']),
                'historical executable role or identity mismatch: '+role)
        if ':' in role:
            require(record['sha256']==pins['lean_release_binaries_sha256'][name],
                    'historical Lean/C++ runtime pin mismatch: '+role)


def audit_economics(item,plan,allow_smoke):
    pairs=item['pairs'];checked={}
    require(pairs and [p['repetition'] for p in pairs]==list(range(len(pairs))),'missing, duplicate or reordered paired runs')
    for pair in pairs:
        require(pair['completed'] is True and sorted(pair['order'])==['direct','full_export','state'],'incomplete primary triple')
        for arm in ('state','full_export','direct'):
            require(pair[arm]['completed'] is True,'unfinished primary lifetime')
            for field in ('wall_seconds','cpu_seconds'):
                value=pair[arm][field]
                require(type(value) in (int,float) and math.isfinite(value) and value>0,'invalid lifetime measurement')
    for i,(candidate,comparator) in enumerate((('state','direct'),('state','full_export'),('full_export','direct'))):
        for field in ('wall_seconds','cpu_seconds'):
            values=[dict(apply_wall_seconds=p[candidate][field],direct_wall_seconds=p[comparator][field]) for p in pairs]
            rebuilt=economics(values,seed=20261024+i)
            stored=item['economics'][candidate+'_vs_'+comparator+'_'+field]
            for key,value in rebuilt.items():
                if allow_smoke and len(pairs)<5 and key in ('status','passed'):continue
                require(stored[key]==value,'economic statistic does not recompute: '+key)
            require(stored['candidate']==candidate and stored['comparator']==comparator and stored['measurement']==field and
                    stored['reduction_percent']==100*(1-rebuilt['median_ratio']) and
                    stored['speedup']==1/rebuilt['median_ratio'],'economic label/percentage mismatch')
            checked[candidate+'_vs_'+comparator+'_'+field]=rebuilt
    for variant in ('early-definition','unrelated-definition','restore-early-definition','restore-unrelated-definition'):
        positions=[i for i,s in enumerate(plan) if s['name']==variant]
        require(positions,'missing edit economic series')
        for comparator in ('direct','full_export'):
            values=[]
            for pair in pairs:
                candidate=sum(pair['state']['steps'][i]['apply_wall_seconds'] for i in positions)
                other=sum(pair[comparator]['commands'][i+1]['wall_seconds'] if comparator=='direct' else
                          pair[comparator]['steps'][i]['apply_wall_seconds'] for i in positions)
                values.append(dict(apply_wall_seconds=candidate,direct_wall_seconds=other))
            rebuilt=economics(values,seed=20261030);stored=item['warm_edit_economics'][variant]['state_vs_'+comparator]
            for key,value in rebuilt.items():
                if allow_smoke and len(pairs)<5 and key in ('status','passed'):continue
                require(stored[key]==value,'edit economic statistic does not recompute')
            require(stored['updates_per_pair']==len(positions),'edit sample count mismatch')
            checked[variant+'_state_vs_'+comparator]=rebuilt
    return checked


def replay_profile(store,profile,item,args,report):
    legacy=item['full_export_witness'];witness=item['state_witness']
    require(legacy['completed'] is True and legacy['correctness_passed'] is True and witness['completed'] is True,
            'incomplete full/state input witnesses')
    plan=decode(store.read('sources/'+profile+'/plan.json'))
    require(len(plan)==4*report['cycles'] and len(legacy['steps'])==len(witness['steps'])==len(plan),
            'missing source revisions or input witnesses')
    for i,step in enumerate(plan,1):step['revision']=i
    baseline=store.blob(legacy['genesis']['baseline_witness']);baseline_sha=sha(baseline)
    require(baseline_sha==legacy['genesis']['export_sha256']==witness['genesis']['export_sha256'],
            'full/state genesis input differs')
    folder=args.out/'profiles'/profile
    baseline_index,baseline_process=fresh_index(baseline,args,folder/'baseline-index')
    records={0:baseline_index};indices=[];steps=[];raw=baseline
    baseline_sources=source_set(store,profile,0)
    initial_hash=sha(canonical(baseline_sources))
    require(witness['genesis']['source_root']==initial_hash,'genesis source capture differs')
    all_exports={baseline_sha:legacy['genesis']['baseline_witness']}
    for observed in legacy['steps']:
        if observed.get('export_witness'):
            descriptor=observed['export_witness'];all_exports[descriptor['uncompressed_sha256']]=descriptor
    observation=dict(profile=profile,baseline_sha256=baseline_sha,obligation_count=baseline_index['count'],
        baseline_full_index_process=baseline_process,steps=[],primary_pairs=[],declaration_witnesses_checked=0,
        primary_transition_count=0,fresh_kernel_processes=0)
    # Rebuild every exact changed input independently, without StateChainSession.
    state_session='witness-state/'+profile+'/session';legacy_session='profiles/'+profile+'/pair-0/session'
    state_gen=witness['genesis'];legacy_gen=legacy['genesis']
    first_state=decode(store.blob(witness['steps'][0]['result_witness']))
    first_legacy=decode(store.blob(legacy['steps'][0]['result_witness']))
    audit_policy(first_state['producer_provenance'],report,'state')
    audit_policy(first_legacy['producer_provenance'],report,'full_export')
    audit_genesis(store,state_session,state_gen,baseline_index,baseline_sha,first_state['producer_provenance'],initial_hash)
    audit_genesis(store,legacy_session,legacy_gen,baseline_index,baseline_sha,first_legacy['producer_provenance'],initial_hash)
    parent_index=baseline_index;parent_state=state_gen['state_id'];parent_head=state_gen['head_id']
    parent_evidence=state_gen['evidence_id'];sources=baseline_sources
    for step,old,new in zip(plan,legacy['steps'],witness['steps']):
        expected=dict(step,export_sha256=old['snapshot']['sha256'],export_bytes=old['snapshot']['bytes'],
                      delta_sha256=old['receipt_audit']['delta_sha256'])
        require(new['snapshot']['export_sha256']==expected['export_sha256'] and
                new['snapshot']['export_bytes']==expected['export_bytes'],'state/full explicit export parity missing')
        result=decode(store.blob(new['result_witness']))
        provisional=index_witness(parent_index,
            public_envelope(decode(store.object(state_session,'records',result['evidence_id'])),STATE_ACCEPTANCE)['identity'])
        checked=audit_step(store,state_session,result,parent_index,provisional,expected,parent_state,parent_head,
                           parent_evidence,sources,state_gen,'state')
        raw=compose(raw,checked['delta'],step['claimed_names'])
        require(sha(raw)==expected['export_sha256'] and len(raw)==expected['export_bytes'],
                'independently composed export differs from full-export oracle bytes')
        require(expected['export_sha256'] in all_exports and store.blob(all_exports[expected['export_sha256']])==raw,
                'exact full-input witness missing or differs')
        current,index_process=fresh_index(raw,args,folder/('revision-%03d'%step['revision'])/'full-index')
        require(current==provisional,'state receipt fingerprints differ from fresh complete typed index')
        require(sha(canonical(current))==old['full_index_sha256']==new['independent_audit']['index_sha256'],
                'recorded index identity differs from actual fresh full index')
        old_result=decode(store.blob(old['result_witness']))
        old_parent_head=legacy_gen['head_id'] if step['revision']==1 else legacy['steps'][step['revision']-2]['revision_chain']['head_id']
        old_parent_evidence=legacy_gen['evidence_id'] if step['revision']==1 else legacy['steps'][step['revision']-2]['evidence_id']
        old_parent_export=baseline_sha if step['revision']==1 else legacy['steps'][step['revision']-2]['snapshot']['sha256']
        audited_old=audit_step(store,legacy_session,old_result,parent_index,current,expected,old_parent_export,
            old_parent_head,old_parent_evidence,sources,legacy_gen,'full_export')
        require(checked['delta']==audited_old['delta'],'full/state issuer consumed different actual changed rows')
        audit_process(store,old['direct_rust'],0,sha(raw),
            expected_binary=report['binary_sha256']['full_checker']['path'],snapshot=old['snapshot'])
        audit_process(store,new['direct_rust'],0,sha(raw),
            expected_binary=report['binary_sha256']['full_checker']['path'],
            snapshot=dict(path=new['snapshot']['path'],sha256=sha(raw),bytes=len(raw),seals=new['snapshot']['seals']))
        if step['revision']<=4:
            for name in ('leanchecker','leanchecker-paranoid'):
                binary=report['binary_sha256'].get(profile+':'+name)
                if binary is None:
                    require(args.allow_smoke,'missing pinned independent checker identity')
                    continue
                audit_process(store,old['representative_cpp'][name],0,sha(raw),expected_binary=binary['path'],
                    snapshot=old['snapshot'],cpp=True)
                audit_process(store,new['additional_oracles'][name],0,sha(raw),expected_binary=binary['path'],
                    snapshot=dict(path=new['snapshot']['path'],sha256=sha(raw),bytes=len(raw),seals=new['snapshot']['seals']),cpp=True)
        kernels=run_kernels(raw,args,folder/('revision-%03d'%step['revision'])/'fresh-kernels',0,step['revision']<=4)
        observation['fresh_kernel_processes']+=len(kernels)
        if step['state'] in records:require(current==records[step['state']],'restored source state has changed semantic identity')
        records[step['state']]=current;indices.append(current);steps.append(expected)
        observation['declaration_witnesses_checked']+=2*current['count']
        observation['steps'].append(dict(revision=step['revision'],export_sha256=sha(raw),export_bytes=len(raw),
            state_id=result['state_id'],index_sha256=sha(canonical(current)),checked=checked['checked'],reused=checked['reused'],
            full_index_process=index_process,kernels=kernels))
        parent_index,parent_state,parent_head,parent_evidence,sources=(current,result['state_id'],result['revision_chain']['head_id'],
            result['evidence_id'],checked['sources'])
    require(witness['cold_replay']['passed'] is True and witness['cold_replay']['expected_head']==parent_head==
            witness['cold_replay']['actual_head'] and witness['cold_replay']['state_id']==parent_state and
            witness['cold_replay']['ready']['replayed_revisions']==len(plan),'cold replay witness mismatch')
    for key,reference in item['references'].items():
        audit_reference(store,reference,records[int(key)],report['binary_sha256']['indexer']['path'])
    for pair in item['pairs']:
        pair_observation=dict(repetition=pair['repetition'],arms={})
        for kind in ('state','full_export'):
            arm=pair[kind];session='primary/'+profile+'/pair-'+str(pair['repetition'])+'/'+kind+'/session'
            genesis=arm['genesis'];audit_policy(arm['steps'][0]['producer_provenance'],report,kind)
            audit_genesis(store,session,genesis,baseline_index,baseline_sha,
                arm['steps'][0]['producer_provenance'],initial_hash)
            require(genesis['source_root']==initial_hash and len(arm['steps'])==len(plan),'primary source/lifetime input mismatch')
            parent_index=baseline_index;parent_head=genesis['head_id'];parent_evidence=genesis['evidence_id']
            parent_state=genesis.get('state_id',baseline_sha);sources=baseline_sources
            for step,current,result in zip(steps,indices,arm['steps']):
                checked=audit_step(store,session,result,parent_index,current,step,parent_state,parent_head,
                    parent_evidence,sources,genesis,kind)
                require(checked['index_sha256']==result['independent_audit']['index_sha256'] if kind=='state' else True,
                        'primary live-key audit index mismatch')
                observation['primary_transition_count']+=1
                observation['declaration_witnesses_checked']+=current['count']
                parent_index,parent_head,parent_evidence,sources=current,checked['head_id'],checked['evidence_id'],checked['sources']
                parent_state=checked['state_id'] if kind=='state' else step['export_sha256']
            require(arm['final_head']==parent_head and arm['final_evidence']==parent_evidence,'primary final head mismatch')
            pair_observation['arms'][kind]=dict(transitions=len(plan),final_head=parent_head,final_evidence=parent_evidence)
        commands=pair['direct']['commands'];require(len(commands)==len(plan)+1,'direct lifetime lacks genesis/revision checks')
        for revision,record in enumerate(commands):
            require(record['revision']==revision,'direct command order mismatch')
            identity=baseline_sha if revision==0 else steps[revision-1]['export_sha256']
            audit_process(store,record,0,identity,expected_binary=report['binary_sha256']['full_checker']['path'],
                          snapshot=record['snapshot'])
        observation['primary_pairs'].append(pair_observation)
    observation['economics']=audit_economics(item,plan,args.allow_smoke)
    observation['passed']=True
    return observation


def required_controls(repo):
    tree=ast.parse((repo/'experiments/incremental/test_state_controls.py').read_text())
    values=[ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and
            any(isinstance(t,ast.Name) and t.id=='REQUIRED_CONTROLS' for t in node.targets)]
    require(len(values)==1 and type(values[0]) is tuple and len(set(values[0]))==len(values[0]),'invalid qualified control inventory')
    return set(values[0])


def audit_control_inventory(summary,inventory):
    controls=summary['controls']
    require(type(controls) is list and len(controls)==len(inventory) and
            {c['name'] for c in controls}==inventory==set(summary['required_controls']) and
            all(c.get('passed') is True for c in controls),'missing or duplicated adversarial controls')
    return controls


def replay_controls(root,args):
    root=root.resolve();summary=decode((root/'summary.json').read_bytes())
    require(summary['schema']=='mathgraph.authenticated-state-controls.v1' and summary['passed'] is True and
            summary['source_sha']==args.source,'unqualified, failed or foreign-source controls')
    controls=audit_control_inventory(summary,required_controls(args.repo))
    by_name={c['name']:c for c in controls}
    baseline_path=Path(by_name['verified-baseline-independent-oracles']['baseline']['path'])
    historical_root=baseline_path.parent.parent
    def read(path):
        path=Path(path)
        if path.is_absolute():
            require(path.is_relative_to(historical_root),'control path outside evidence')
            path=path.relative_to(historical_root)
        return checked_bytes(root,str(path))
    def export(descriptor):
        raw=gzip.decompress(read(descriptor['path']))
        require(sha(raw)==descriptor['export_sha256'] and len(raw)==descriptor['export_bytes'],'control export identity mismatch')
        return raw
    parent=export(by_name['early-edit-full-index-partition-and-kernel-parity']['exact_input'])
    observed=dict(profile=summary['profile'],control_count=len(controls),fresh_kernel_processes=0,
                  negatives=[],corruptions=[],delta_controls=[])
    for c in controls:
        if 'actual_delta' in c:
            actual=c['actual_delta'];raw=read(actual['path'])
            require(sha(raw)==actual['sha256'],'negative actual delta identity mismatch')
            envelope=decode(read(actual['attestation_path']))
            require(type(envelope) is dict and set(envelope)=={'payload','hmac_sha256'} and
                    type(envelope['payload']) is dict,'missing exact negative transition envelope')
            observed['delta_controls'].append(dict(name=c['name'],delta_sha256=sha(raw),bytes=len(raw)))
        if 'corrupted_object' in c:
            corruption=c['corrupted_object'];raw=gzip.decompress(read(corruption['path']))
            require(sha(raw)==corruption['corrupted_content_sha256'] and
                    sha(raw)!=corruption['original_content_sha256'] and raw.endswith(b'corrupt') and
                    sha(raw[:-7])==corruption['original_content_sha256'],'corruption falsifier bytes do not support stated mutation')
            require(c.get('accepted_records_unchanged') is True and c.get('poisoned') is True and
                    type(c.get('observed_refusal')) is str,'corruption did not record refusal boundary')
            observed['corruptions'].append(c['name'])
        if 'exact_negative_export' in c:
            raw=export(c['exact_negative_export']);attempt=c['attempt_identity']
            require(c['name'] in {'unused-malformed-dag-zero-selected','signed-invalid-definition-proof'},'unexpected kernel negative')
            require(c['result']['status']=='REJECTED' and c['result']['checker_result']['code']==1 and
                    c['result']['evidence_id'] is None and attempt['state_id'] is None and
                    attempt['scope']=='unaccepted_attempt_for_independent_oracle_only' and
                    attempt['export_sha256']==sha(raw)==c['exact_negative_export_sha256'] and
                    attempt['export_bytes']==len(raw),'negative input masquerades as accepted state')
            actual=c['actual_delta'];envelope=decode(read(actual['attestation_path']))
            payload=public_envelope(envelope,STATE_TRANSITION);delta=read(actual['path'])
            require(payload['delta_sha256']==attempt['delta_sha256']==sha(delta) and
                    payload['base_state_id']==attempt['parent_state_id']==actual['parent_state_id'] and
                    payload['base_evidence_id']==actual['parent_evidence_id'],'negative attempted input parent/delta mismatch')
            require(compose(parent,delta,payload['changed_names'])==raw,'negative full export is stale or differs from attempted delta')
            historical=c['independent_kernel_rejections']
            require(set(historical)=={'rust','leanchecker','leanchecker-paranoid'} and
                    all(r['returncode']==1 and r['timed_out'] is False for r in historical.values()),
                    'negative lacks actual three-kernel rejection controls')
            folder=args.out/'controls'/summary['profile']/c['name']
            kernels=run_kernels(raw,args,folder,1,True)
            observed['fresh_kernel_processes']+=len(kernels)
            observed['negatives'].append(dict(name=c['name'],export_sha256=sha(raw),export_bytes=len(raw),kernels=kernels))
    require(len(observed['negatives'])==2 and len(observed['corruptions'])==10,'negative/corruption coverage incomplete')
    observed['passed']=True
    return observed


def run(args):
    args.repo=args.repo.resolve();args.benchmark=args.benchmark.resolve();args.out=args.out.resolve()
    args.out.mkdir(parents=True,exist_ok=False)
    summary=decode((args.benchmark/'summary.json').read_bytes())
    report=dict(schema='mathgraph.authenticated-state-independent-replay.v1',source_sha=args.source,
        completed=False,passed=False,profiles={},controls=[],historical_hmac_reauthenticated=False,
        boundary='Public historical issuer envelope domains and content addresses checked; original HMAC secret unavailable. '
            'Fresh full indexes and actual kernels independently establish exact-input identity and verdict agreement. '
            'Historical timing observations are recomputed arithmetically, not remeasured.',
        cycles=summary.get('cycles'),fresh_kernel_processes=0,primary_transition_count=0,
        declaration_witnesses_checked=0,control_count=0)
    def flush():(args.out/'summary.json').write_bytes(canonical(report)+b'\n')
    flush()
    try:
        require(git_sha(args.source),'exact 40-character Git source SHA required')
        require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.repo,text=True).strip()==args.source,
                'independent reader checkout is not exact qualified source')
        require(not subprocess.check_output(['git','status','--porcelain','--','src','Cargo.toml','Cargo.lock'],
                    cwd=args.repo,text=True).strip(),'fresh checker sources are dirty')
        require(summary['schema']=='mathgraph.authenticated-export-state-economics.v1' and
                summary['source_sha']==args.source and summary['completed'] is True and
                summary['correctness_passed'] is True and summary['source_and_binary_stable'] is True,
                'missing, failed, source-drifted or foreign benchmark')
        if not args.allow_smoke:
            require(summary['qualified'] is True and summary['source_tracked_clean'] is True and
                summary['repetitions']==5 and summary['cycles']==10 and set(summary['profiles'])=={'original','expanded'},
                'qualification requires exact-source five40-update triples on both real profiles')
            require(len(args.controls)==2,'both real-profile control suites required')
            require(not subprocess.check_output(['git','status','--porcelain','--','experiments/incremental','.github/workflows'],
                cwd=args.repo,text=True).strip(),'qualified runtime/reader/pin/workflow sources are dirty')
        audit_source_manifest(args.repo,summary['source_sha256'])
        pins=decode((args.repo/'experiments/incremental/pins.json').read_bytes())
        audit_historical_tool_pins(summary,pins)
        require(sha(args.cpp.read_bytes())==pins['lean_release_binaries_sha256']['leanchecker'] and
                sha(args.paranoid.read_bytes())==pins['lean_release_binaries_sha256']['leanchecker-paranoid'],
                'independent normal/paranoid C++ runtime pin mismatch')
        binary_before={name:sha(getattr(args,name).read_bytes()) for name in ('rust','indexer','cpp','paranoid')}
        report['binary_sha256']=binary_before
        report['rust_binary_scope']='Freshly built from exact checked-out research source; cross-host bit-identical Rust binary is not assumed.'
        store=Store(args.benchmark,summary)
        for profile,item in summary['profiles'].items():
            observation=replay_profile(store,profile,item,args,summary)
            report['profiles'][profile]=observation
            for field in ('fresh_kernel_processes','primary_transition_count','declaration_witnesses_checked'):
                report[field]+=observation[field]
            flush();print(json.dumps(dict(profile=profile,passed=True,primary_transitions=observation['primary_transition_count'])),flush=True)
        for root in args.controls:
            observation=replay_controls(root,args);report['controls'].append(observation)
            report['control_count']+=observation['control_count'];report['fresh_kernel_processes']+=observation['fresh_kernel_processes'];flush()
        if not args.allow_smoke:
            require({c['profile'] for c in report['controls']}=={'original-v1','std-hashmap-expanded-v1'},'control profiles missing or duplicated')
        require({name:sha(getattr(args,name).read_bytes()) for name in binary_before}==binary_before,'independent executed binary changed')
        report.update(completed=True,passed=True,archive_objects_validated=len(store.archives_checked),
                      all_qualified_fingerprints_selected_sets_and_verdicts_agree=True)
        flush();print(json.dumps(dict(completed=True,passed=True,source_sha=args.source,
            fresh_kernel_processes=report['fresh_kernel_processes'],primary_transition_count=report['primary_transition_count'])),flush=True)
    except Exception as error:
        report['error']=repr(error);flush();raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('benchmark','repo','rust','indexer','cpp','paranoid','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--controls',type=Path,action='append',default=[])
    parser.add_argument('--source',required=True)
    parser.add_argument('--timeout',type=int,default=300)
    parser.add_argument('--allow-smoke',action='store_true')
    args=parser.parse_args()
    for name in ('rust','indexer','cpp','paranoid'):setattr(args,name,getattr(args,name).resolve())
    run(args)


if __name__=='__main__':main()
