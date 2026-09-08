#!/usr/bin/env python3
"""Rapid, evidence-gated search. The full Arena is a qualification gate, not the search loop."""
import difflib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
import profile_v89 as v
import eval_leaf_v91 as leaf
import patch_prune_dm_v88 as prune

ROOT = Path(os.environ.get('V92_ROOT', '/tmp/v92'))
OUT = ROOT / 'out'
BASE_EVAL = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
BASE_UTIL = 'a0fab9f758a6fe947585d866d98665d9512c1a2c'
BASE_TESTS = '2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc'
EXPECTED = {'init-prelude':'0f7993829d6fcc8b07d177a3879024fbbc8908f7c6fd9cb2fa93370e4397e204',
            'cedar':'2baf8459f06272118f605deed8b11f4d5953231f7b8f147e6d08823c7dfa49a1',
            'mathlib':'ca2ec20fd063b61e71867b2975c81bd989af9f879b4886b8f08cd23c767a47bb'}
VAR = '''            Expr::Var { dbj_idx, .. } => {
                let v = env.lookup(dbj_idx).expect("eval: loose bvar");
                return self.force_thunk(depth, v);
            }
'''
LITS = '''            Expr::NatLit { ptr, .. } => return value::mk_natlit(self.arena, ptr),
            Expr::StringLit { ptr, .. } => return value::mk_strlit(self.arena, ptr),
'''
HEAD = leaf.OLD.split('        if e.num_loose_bvars()', 1)[0]
TAIL = leaf.OLD[len(HEAD):]
assert leaf.NEW == HEAD + '        // Leaf values need neither environment projection nor cache dispatch.\n        match *self.ctx.read_expr_ref(e) {\n' + VAR + LITS + '            _ => {}\n        }\n' + TAIL
VARIANTS = [('control',False,False,False),('var',True,False,False),('literals',False,True,False),
            ('leaf',True,True,False),('prune',False,False,True),('var_prune',True,False,True),
            ('literals_prune',False,True,True),('leaf_prune',True,True,True)]

def save(obj, name='summary.json'):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def transform(source, var=False, lits=False):
    if not (var or lits):
        return source
    replacement = HEAD + '        // Direct evaluation of selected leaves.\n        match *self.ctx.read_expr_ref(e) {\n'
    if var: replacement += VAR
    if lits: replacement += LITS
    replacement += '            _ => {}\n        }\n' + TAIL
    assert source.count(leaf.OLD)==1
    result=source.replace(leaf.OLD,replacement)
    assert result.replace(replacement,leaf.OLD)==source
    return result

def source_pair(base_eval, base_util, variant):
    _,var,lits,keep=variant
    return transform(base_eval,var,lits), prune.transform(base_util) if keep else base_util

def setup():
    ROOT.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    v.ROOT=ROOT; v.OUT=OUT
    if not (ROOT/'control').exists():
        v.call(['git','clone','-q','https://github.com/metalogiclabs/mathgraph-lean-kernel',str(ROOT/'control')])
    v.call(['git','-C',str(ROOT/'control'),'checkout','-q',v.BASE])
    assert v.capture(['git','-C',str(ROOT/'control'),'rev-parse','HEAD']).stdout.decode().strip()==v.BASE
    assert v.blob((ROOT/'control/src/eval.rs').read_bytes())==BASE_EVAL
    assert v.blob((ROOT/'control/src/util.rs').read_bytes())==BASE_UTIL
    assert v.blob((ROOT/'control/src/tests.rs').read_bytes())==BASE_TESTS
    assert v.blob((ROOT/'control/Cargo.lock').read_bytes())=='32f3b6ee113788997b7f2f95a803ba0684131e49'
    if not (ROOT/'work').exists():
        shutil.copytree(ROOT/'control',ROOT/'work',ignore=shutil.ignore_patterns('.git','target'))
    if not (ROOT/'arena/.git').exists():
        v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(ROOT/'arena')])
    v.call(['git','-C',str(ROOT/'arena'),'checkout','-q',v.ARENA])
    assert v.capture(['git','-C',str(ROOT/'arena'),'rev-parse','HEAD']).stdout.decode().strip()==v.ARENA
    (ROOT/'config.json').write_text(json.dumps(v.CONFIG)+'\n')
    for corpus,sha in EXPECTED.items():
        p=ROOT/'arena/_build/tests'/(corpus+'.ndjson')
        if not p.exists() or v.sha_file(p)!=sha:
            v.call(['./lka.py','build-test',corpus],cwd=ROOT/'arena',log='build-'+corpus+'.log',timeout=3600)
        assert v.sha_file(p)==sha, 'Frozen corpus mismatch: '+corpus
    save({'base':v.BASE,'arena':v.ARENA,'inputs':EXPECTED,'source_commit':os.environ.get('GITHUB_SHA'),
          'source_hashes':{'eval':BASE_EVAL,'util':BASE_UTIL,'tests':BASE_TESTS},'variants':[x[0] for x in VARIANTS]},'source.json')

def install(variant):
    name=variant[0]
    olde=(ROOT/'control/src/eval.rs').read_text()
    oldu=(ROOT/'control/src/util.rs').read_text()
    newe,newu=source_pair(olde,oldu,variant)
    for path,text in [('src/eval.rs',newe),('src/util.rs',newu)]:
        p=ROOT/'work'/path
        p.write_text(text)
        os.utime(p,None)
        assert p.read_text()==text
    assert (ROOT/'work/src/tests.rs').read_bytes()==(ROOT/'control/src/tests.rs').read_bytes()
    assert (ROOT/'work/Cargo.lock').read_bytes()==(ROOT/'control/Cargo.lock').read_bytes()
    src=ROOT/'sources'/name
    src.mkdir(parents=True,exist_ok=True)
    for path,text,old in [('eval.rs',newe,olde),('util.rs',newu,oldu)]:
        (src/path).write_text(text)
        (OUT/(name+'.'+path+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='control/src/'+path,tofile='candidate/src/'+path)))
    return {p:v.blob((src/p).read_bytes()) for p in ['eval.rs','util.rs']}

def build(name,variant):
    hashes=install(variant)
    target=ROOT/'target-search'
    env=dict(os.environ,CARGO_TARGET_DIR=str(target),CARGO_INCREMENTAL='0',RUSTFLAGS='-C target-cpu=native')
    v.call(['cargo','build','--release','--locked','-q'],cwd=ROOT/'work',env=env,log=name+'.build.log',timeout=3600)
    binary=ROOT/'binaries'/name
    binary.parent.mkdir(exist_ok=True)
    shutil.copy2(target/'release/sokonanoda',binary)
    return {'path':str(binary),'sha256':v.sha_file(binary),'source_hashes':hashes,'flags':env['RUSTFLAGS']}

def quick_input(corpus,baseline):
    full=ROOT/'arena/_build/tests'/(corpus+'.ndjson')
    lines=full.read_bytes().splitlines(keepends=True)
    assert lines
    # A prefix preserves all preceding declarations. It is a screening workload, not a held-out test.
    n=min(len(lines),128)
    while True:
        p=ROOT/'arena/_build/tests'/('rapid-'+corpus+'.ndjson')
        p.write_bytes(b''.join(lines[:n]))
        row=v.run_binary(baseline,'rapid-'+corpus,'calibrate-'+corpus,timeout=180)
        if row['rc']!=0:
            raise RuntimeError('Prefix is not a valid checker input: '+corpus)
        if row['seconds']>=1.5 or n==len(lines):
            assert row['seconds']<=60, 'Screening input too slow; reduce the prefix'
            return {'path':str(p),'sha256':v.sha_file(p),'lines':n,'total_lines':len(lines),'baseline_seconds':row['seconds']}
        n=min(len(lines),n*2)

def screen(binaries, fixtures, summary):
    names=list(binaries)
    results={name:{} for name in names}
    for corpus in fixtures:
        key='rapid-'+corpus
        ref=v.run_binary(binaries['control']['path'],key,corpus+'.control.reference')
        assert ref['rc']==0
        for name in names:
            row=v.run_binary(binaries[name]['path'],key,corpus+'.'+name+'.replay')
            assert row['rc']==0 and row['stdout_sha256']==ref['stdout_sha256'] and row['stderr_sha256']==ref['stderr_sha256'], 'Replay mismatch: '+name+'/'+corpus
        rows=[]
        for i in range(4):
            for name in (names if i%2==0 else list(reversed(names))):
                row=v.run_binary(binaries[name]['path'],key,corpus+'.'+name+'.'+str(i))
                assert row['rc']==0 and row['stdout_sha256']==ref['stdout_sha256'] and row['stderr_sha256']==ref['stderr_sha256']
                rows.append({'arm':name,'pass':i,**row})
        control=statistics.median(r['seconds'] for r in rows if r['arm']=='control')
        for name in names:
            times=[r['seconds'] for r in rows if r['arm']==name]
            results[name][corpus]={'median':statistics.median(times),'delta_percent':100*(statistics.median(times)/control-1),'runs':times}
        summary['screen']={'fixtures':fixtures,'results':results,'raw':rows if corpus==list(fixtures)[-1] else []}
        save(summary)
    for name in names:
        if name=='control':continue
        ds=[results[name][c]['delta_percent'] for c in fixtures]
        results[name]['geomean_delta_percent']=100*(math.prod(1+d/100 for d in ds)**(1/len(ds))-1)
    ranked=sorted((n for n in names if n!='control'),key=lambda n:results[n]['geomean_delta_percent'])
    # A short prefix can only nominate a candidate; it cannot establish a full-corpus gain.
    winner=next((n for n in ranked if results[n]['geomean_delta_percent']<=-3 and
                 all(results[n][c]['delta_percent']<=2 for c in fixtures)),None)
    summary['screen']={'fixtures':fixtures,'results':results,'ranking':ranked,'winner':winner,
                       'decision':'QUALIFY' if winner else 'NO_SCREENING_WINNER'}
    save(summary)
    return winner

def qualify(winner, summary):
    # Fresh PGO for each arm, identical training and flags. The search binaries are never promoted.
    shutil.rmtree(ROOT/'candidate',ignore_errors=True)
    shutil.copytree(ROOT/'control',ROOT/'candidate',ignore=shutil.ignore_patterns('.git','target'))
    variant=next(x for x in VARIANTS if x[0]==winner)
    e,u=source_pair((ROOT/'control/src/eval.rs').read_text(),(ROOT/'control/src/util.rs').read_text(),variant)
    (ROOT/'candidate/src/eval.rs').write_text(e)
    (ROOT/'candidate/src/util.rs').write_text(u)
    v.qualification()
    summary['qualification']=json.loads((OUT/'qualification.json').read_text())
    binaries={arm:v.build_pgo(arm) for arm in ['control','candidate']}
    summary['qualification_binaries']=binaries
    save(summary)
    v.measure(binaries,summary)
    ds=[summary['corpora'][c]['delta_percent'] for c in ['std','cedar','mathlib']]
    summary['decision']='FULL_GAIN_CONFIRMED__RELEASE_BLOCKED_KNOWN_FIXTURES' if summary['timing_decision']=='REPEAT_AND_ABLATE' else 'REJECT_OR_INCONCLUSIVE'
    summary['release_promoted']=False
    save(summary)
    if summary['decision'].startswith('FULL_GAIN_CONFIRMED'):
        print('V92_FULL_GAIN_CONFIRMED='+winner,flush=True)

def main():
    setup()
    summary={'schema':1,'status':'SEARCHING','release_promoted':False,'base':v.BASE,'arena':v.ARENA,'corpora':{}}
    save(summary)
    try:
        binaries={}
        for variant in VARIANTS:
            binaries[variant[0]]=build(variant[0],variant)
            summary['binaries']=binaries
            save(summary)
        fixtures={c:quick_input(c,binaries['control']['path']) for c in ['cedar','mathlib']}
        save(fixtures,'screen-inputs.json')
        winner=screen(binaries,fixtures,summary)
        if winner:
            qualify(winner,summary)
        else:
            summary['decision']='NO_SCREENING_WINNER__NO_FULL_BENCHMARK'
        summary['status']='COMPLETE'
    except BaseException as exc:
        summary['status']='FAILED';summary['error']=repr(exc)
        save(summary)
        raise
    save(summary)
    print('V92_DECISION='+summary['decision'],flush=True)
    print('V92_RELEASE_PROMOTED=false',flush=True)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        assert transform(leaf.OLD,True,True).replace('        // Direct evaluation of selected leaves.','        // Leaf values need neither environment projection nor cache dispatch.')==leaf.NEW
        for variant in VARIANTS:
            e,u=source_pair(leaf.OLD,'x',variant) if not variant[3] else (transform(leaf.OLD,variant[1],variant[2]),'x')
            assert e.count('pub(crate) fn eval(')==1
            assert e.count('Expr::Var { dbj_idx, .. } =>')==int(variant[1])
            assert e.count('Expr::NatLit { ptr, .. } =>')==int(variant[2])
        print('V92_PATCH_SELF_TEST=PASS',flush=True)
    else:
        v.ROOT=ROOT;v.OUT=OUT
        main()
