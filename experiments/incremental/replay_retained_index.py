#!/usr/bin/env python3
"""Independent retained-SCC protocol falsifiers; no kernel acceptance inferred.

Synthetic typed DAG/metadata graphs may have incomplete mathematical meaning.
The qualified 4496042 full Python index, untouched native full finish and a new
full native parse independently observe every reconstructed composite.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

OUT=None
SOURCE='4496042c75368f6c35675a9b131c960080afa518'
BASELINE_ENGINE_SHA256='216662587fafcb6880f4354e3794dcd766cb305d4c098e348dcf33326c513905'
SIMPLE={'def','thm','opaque','axiom'}
DECL=SIMPLE|{'quot','inductive'}
META={'meta':{'lean':{'version':'4.35.0','githash':'independent-retained-fixture'},
      'exporter':{'name':'lean4export','version':'3.1.0'},'format':{'version':'3.1.0'}}}


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def stream(rows):return b''.join(canonical(row)+b'\n' for row in rows)
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')

def strict(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key: '+key)
        result[key]=value
    return result

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1<<20),b''):h.update(data)
    return h.hexdigest()


def declaration(name,edges=(),kind='def',hints='abbrev'):
    body=dict(name=name,levelParams=[],type=1)
    if kind=='axiom':body['isUnsafe']=False
    else:
        body.update(value=0,all=list(edges))
        if kind=='def':body.update(hints=hints,safety='safe')
        if kind=='opaque':body['isUnsafe']=False
    return {kind:body}


def graph(edges,names=None):
    names=names or ['node'+str(i) for i in range(len(edges))]
    rows=[copy.deepcopy(META)]
    rows += [{'in':i+1,'str':{'pre':0,'str':name}} for i,name in enumerate(names)]
    rows += [{'il':1,'succ':0},{'ie':0,'sort':0},{'ie':1,'sort':1}]
    rows += [declaration(i+1,[j+1 for j in deps]) for i,deps in enumerate(edges)]
    return rows


def replacement(rows,position,**changes):
    old=[r for r in rows if set(r)&SIMPLE][position]
    row=copy.deepcopy(old)
    row[next(iter(row))].update(changes)
    return row


def materialize(rows,delta):
    replacements={}
    dags=[]
    for row in delta:
        tag=next(iter(set(row)&SIMPLE),None)
        if tag:replacements[(tag,row[tag]['name'])]=row
        else:dags.append(row)
    result=[r for r in rows if not(set(r)&DECL)]+dags
    for row in rows:
        tags=set(row)&DECL
        if not tags:continue
        tag=next(iter(tags))
        result.append(replacements.pop((tag,row[tag]['name']),row) if tag!='inductive' else row)
    assert not replacements
    return result


def cases():
    result=[]
    def add(name,base,delta,mode='retained',affected=None,reason=None,error=False,malformed=False):
        result.append(dict(name=name,base=base,delta=delta,mode=mode,affected=affected,
                           reason=reason,error=error,malformed=malformed))
    base=graph([[],[0],[1],[]])
    add('fixed-chain',base,[replacement(base,0,hints='opaque')],affected=3)
    add('two-dependent-changes-reverse-row-order',base,
        [replacement(base,1,hints='opaque'),replacement(base,0,hints='opaque')],affected=3)
    restored=copy.deepcopy(base)
    next(r['def'] for r in restored if 'def'in r)['hints']='opaque'
    add('restoration-on-new-owned-baseline',restored,[replacement(restored,0,hints='abbrev')],affected=3)
    add('no-op-replacement',base,[replacement(base,0)],affected=0)
    add('empty-delta',base,[],affected=0)
    add('unused-valid-expression',base,[{'ie':2,'sort':0}],affected=0)
    add('unused-malformed-expression',base,[{'ie':2,'bvar':'not-an-integer'}],affected=0,malformed=True)
    cycle=graph([[1],[0],[0],[2],[]])
    add('cycle-one-member',cycle,[replacement(cycle,0,hints='opaque')],affected=4)
    add('cycle-two-members-reverse-row-order',cycle,
        [replacement(cycle,1,hints='opaque'),replacement(cycle,0,hints='opaque')],affected=4)
    add('cycle-split-fallback',cycle,[replacement(cycle,1,all=[])],mode='full',reason='dependency_edges_changed')
    base2=graph([[],[0],[]])
    add('cycle-created-fallback',base2,[replacement(base2,0,all=[2])],mode='full',reason='dependency_edges_changed')
    retarget=graph([[1],[],[]])
    add('retarget-without-scc-shape-change',retarget,[replacement(retarget,0,all=[3])],mode='full',reason='dependency_edges_changed')
    negatives=graph([[]])
    negatives[1:1]=[{'in':2,'str':{'pre':0,'str':'missingX'}},{'in':3,'str':{'pre':0,'str':'missingY'}}]
    next(r['def'] for r in negatives if 'def'in r)['all']=[2]
    add('unresolved-name-retarget',negatives,[replacement(negatives,0,all=[3])],mode='full',reason='dependency_edges_changed')
    add('self-edge-normalized-away',graph([[]]),[replacement(graph([[]]),0,all=[1])],affected=1)
    builtins=graph([[],[0],[1]],['helper','String.ofList','user'])
    add('builtin-helper-transitive-root',builtins,[replacement(builtins,0,hints='opaque')],affected=3)
    add('builtin-own-fallback',builtins,[replacement(builtins,1,hints='opaque')],mode='full',reason='builtin_declaration_changed')
    axiom=graph([[]],['propext']);axiom[-1]=declaration(1,kind='axiom')
    add('axiom-type-fallback',axiom,[replacement(axiom,0,type=0)],mode='full',reason='axiom_assumption_changed')
    sparse=graph([[]]);sparse[1:1]=[{'in':100,'str':{'pre':0,'str':'sparse'}}]
    add('sparse-hole-unused-builtin',sparse,[{'in':2,'str':{'pre':0,'str':'Nat.add'}}],mode='full',reason='builtin_name_inventory_changed')
    add('sparse-hole-unused-nonbuiltin',sparse,[{'in':2,'str':{'pre':0,'str':'other'}}],affected=0)
    ambiguous=graph([[]]);ambiguous[1:1]=[{'in':100,'str':{'pre':0,'str':'Nat'}},{'in':101,'str':{'pre':0,'str':'Nat.add'}}]
    add('ambiguous-builtin-alternate-typed-path',ambiguous,[{'in':2,'str':{'pre':100,'str':'add'}}],error=True)
    add('ambiguous-builtin-identical-typed-path',ambiguous,[{'in':2,'str':{'pre':0,'str':'Nat.add'}}],error=True)
    mixed=graph([[1],[0],[0],[2],[]])
    # Replace node1 by one inductive type while preserving A<->B metadata SCC.
    d=mixed[-4]['def']
    mixed[-4]={'inductive':{'types':[dict(name=d['name'],levelParams=[],type=1,numParams=0,numIndices=0,
        all=[1,2],ctors=[],numNested=0,isRec=False,isUnsafe=False,isReflexive=False)],'ctors':[],'recs':[]}}
    add('mixed-simple-inductive-scc',mixed,[replacement(mixed,0,hints='opaque')],affected=4)
    add('duplicate-replacement-poisons',base,[replacement(base,0),replacement(base,0)],error=True)
    add('old-expression-redefinition-poisons',base,[{'ie':0,'sort':0}],error=True)
    return result


def invoke(label,args,requests=None,expected=0):
    run=subprocess.run([str(x) for x in args],input=None if requests is None else stream(requests),
                       capture_output=True,timeout=30)
    (OUT/(label+'.stdout')).write_bytes(run.stdout);(OUT/(label+'.stderr')).write_bytes(run.stderr)
    record=dict(command=[str(x) for x in args],returncode=run.returncode,expected=expected,
                stdout_sha256=sha(run.stdout),stderr_sha256=sha(run.stderr))
    write(OUT/(label+'.command.json'),record)
    assert run.returncode==expected,(label,record,run.stderr.decode(errors='replace'))
    return [json.loads(line,object_pairs_hook=strict) for line in run.stdout.splitlines()],record


def arguments():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-session',type=Path,required=True)
    parser.add_argument('--indexer',type=Path,required=True)
    parser.add_argument('--checker',type=Path,required=True)
    parser.add_argument('--baseline-engine',type=Path,required=True,
        help='Unmodified qualified4496042 engine.py, extracted with git show; exact SHA256 is required')
    parser.add_argument('--out',type=Path,required=True)
    return parser.parse_args()


def main(args):
    if not __debug__:raise ValueError('Python audit assertions must be enabled; do not use -O')
    raw=args.baseline_engine.resolve().read_bytes()
    assert sha(raw)==BASELINE_ENGINE_SHA256,'baseline Python full-index oracle is not the qualified449 source'
    frozen=OUT/'qualified_449_full_index.py';frozen.write_bytes(raw)
    spec=importlib.util.spec_from_file_location('qualified_449_full_index',frozen)
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    tools={}
    for name,provided in [('index-session',args.index_session),('export-index',args.indexer),('check-selected',args.checker)]:
        source=provided.resolve();destination=OUT/name
        source_hash=file_hash(source)
        shutil.copyfile(source,destination);destination.chmod(0o500)
        assert file_hash(destination)==source_hash,'tool changed while being captured: '+name
        tools[name]=dict(path=str(destination),input_path=str(source),sha256=source_hash)
    results=[]
    for case in cases():
        name=case['name'];base=OUT/(name+'.baseline.ndjson');delta=OUT/(name+'.delta.ndjson')
        base.write_bytes(stream(case['base']));delta.write_bytes(stream(case['delta']))
        config=OUT/(name+'.config.json')
        cfg=dict(export_file_path=str(base),num_threads=1,nat_extension=True,string_extension=True,
                 permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True)
        write(config,cfg)
        expected=1 if case['error'] else 0
        request=dict(delta_path=str(delta))
        # A second request after a failed mutation must not emit a successful index.
        requests=[request,request] if case['error'] else [request]
        retained,retained_cmd=invoke(name+'-retained',[tools['index-session']['path'],config],requests,expected)
        full,full_cmd=invoke(name+'-full',[tools['index-session']['path'],config,'--full-finish'],requests,expected)
        assert retained[0]['status']==full[0]['status']=='ready'
        assert retained[0]['identity_mode']=='retained' and full[0]['identity_mode']=='full'
        assert canonical(retained[0]['index'])==canonical(oracle.make_index(base))
        assert canonical(full[0]['index'])==canonical(retained[0]['index'])
        if case['error']:
            assert len(retained)==len(full)==2 and retained[1]['status']==full[1]['status']=='error'
            assert 'index' not in retained[1] and 'index' not in full[1]
            results.append(dict(name=name,status='REFUSED_NO_INDEX_SESSION_TERMINATED',commands=[retained_cmd,full_cmd]))
            continue
        assert len(retained)==len(full)==2 and retained[1]['status']==full[1]['status']=='indexed'
        assert canonical(retained[1]['index'])==canonical(full[1]['index'])
        stats=retained[1]['finish_stats']
        assert stats['mode']==case['mode'],(name,stats)
        if case['reason']:assert stats['reason']==case['reason'],(name,stats)
        if case['affected'] is not None:assert stats['affected_declarations']==case['affected'],(name,stats)
        if stats['mode']=='retained':
            old_by_key={d['key']:d for d in retained[0]['index']['declarations']}
            new=retained[1]['index']['declarations']
            affected=sorted(d['key'] for d in new if d['closure']!=old_by_key[d['key']]['closure'])
            changed=[d for d in new if d['own']!=old_by_key[d['key']]['own']]
            assert stats['affected_keys']==affected,(name,stats)
            assert stats['touched_declarations']==stats['affected_declarations']==len(affected)
            assert stats['changed_declarations']==len(changed)
            affected_roots={d['closure'] for d in new if d['key'] in affected}
            assert stats['closure_hashes']==stats['affected_sccs']==len(affected_roots)
            assert stats['changed_sccs']==len({old_by_key[d['key']]['closure'] for d in changed})
            assert stats['recomputed_sccs']==sorted(set(stats['recomputed_sccs']),reverse=True)
            assert len(stats['recomputed_sccs'])==stats['affected_sccs']
        composite=OUT/(name+'.composite.ndjson');composite.write_bytes(stream(materialize(case['base'],case['delta'])))
        assert canonical(retained[1]['index'])==canonical(oracle.make_index(composite)),name
        composite_cfg=OUT/(name+'.composite-config.json');write(composite_cfg,dict(cfg,export_file_path=str(composite)))
        extra=[]
        if case['malformed']:
            indices=OUT/(name+'.indices.json');write(indices,[])
            _,actual=invoke(name+'-genuine-zero-parser',[tools['check-selected']['path'],composite_cfg,indices],expected=1)
            extra.append(actual)
        else:
            parsed,actual=invoke(name+'-fresh-native',[tools['export-index']['path'],composite_cfg])
            assert len(parsed)==1 and canonical(parsed[0])==canonical(retained[1]['index']),name
            extra.append(actual)
        results.append(dict(name=name,status='FULL_INDEX_PARITY',retained_stats=stats,
            baseline_sha256=sha(base.read_bytes()),delta_sha256=sha(delta.read_bytes()),
            composite_sha256=sha(composite.read_bytes()),index_sha256=sha(canonical(retained[1]['index'])),
            commands=[retained_cmd,full_cmd]+extra))
    # Request decoder must reject untrusted persisted-SCC state, not deserialize it.
    for field,value in [('retained_state',{'roots':[]}),('scc_cache_path','unverified.json')]:
        case=cases()[0];name='reject-external-'+field
        base=OUT/'fixed-chain.baseline.ndjson';delta=OUT/'fixed-chain.delta.ndjson';config=OUT/'fixed-chain.config.json'
        response,command=invoke(name,[tools['index-session']['path'],config],[dict(delta_path=str(delta),**{field:value})],1)
        assert len(response)==2 and response[1]['status']=='error' and 'index'not in response[1]
        results.append(dict(name=name,status='REFUSED_UNTRUSTED_CACHE_INPUT',commands=[command]))
    summary=dict(status='PASS_INDEPENDENT_RETAINED_SCC_FIXTURES',fixture_count=len(results),
        tools=tools,helper_sha256=sha(Path(__file__).read_bytes()),oracle_source=SOURCE,
        oracle_source_sha256=sha(raw),cases=results,
        scope=['Synthetic graph identity/parser tests, not kernel acceptance of cyclic or incomplete declarations.',
               'Every success compared retained mode, forced untouched full finish, frozen449 Python complete index; valid composites additionally use fresh native full parsing.',
               'Malformed unused DAG is independently rejected by actual zero-selected parser despite identical index.',
               'Private in-memory retained state is never loaded from untrusted serialized state.'])
    assert len(results)==26,'incomplete independent fixture suite'
    assert file_hash(args.baseline_engine.resolve())==BASELINE_ENGINE_SHA256
    for info in tools.values():assert file_hash(info['path'])==info['sha256']
    summary.update(passed=True,complete=True)
    write(OUT/'summary.json',summary)
    print(json.dumps(dict(status=summary['status'],fixtures=len(results),tool_sha256=tools['index-session']['sha256'])))

if __name__=='__main__':
    args=arguments()
    OUT=args.out.resolve()
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('use a fresh evidence output directory')
    OUT.mkdir(parents=True,exist_ok=True)
    try:
        main(args)
    except Exception as error:
        write(OUT/'summary.json',dict(status='FAIL_INDEPENDENT_RETAINED_SCC_FIXTURES',passed=False,
            complete=False,helper_sha256=file_hash(__file__),oracle_source=SOURCE,error=repr(error)))
        raise
