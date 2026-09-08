#!/usr/bin/env python3
"""V92: tournament the isolated eval leaf fast path by causal subset under fresh PGO."""
import difflib
import json
import os
import shutil
import sys
from pathlib import Path
import profile_v89 as v

BASE_EVAL = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
OLD = '''    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        if e.num_loose_bvars() == 0 && env.lsub().is_none() {
'''
VAR = '''            Expr::Var { dbj_idx, .. } => {
                let v = env.lookup(dbj_idx).expect("eval: loose bvar");
                return self.force_thunk(depth, v);
            }
'''
NAT = '''            Expr::NatLit { ptr, .. } => return value::mk_natlit(self.arena, ptr),
'''
STRING = '''            Expr::StringLit { ptr, .. } => return value::mk_strlit(self.arena, ptr),
'''
VARIANTS = {
    'var': ('var',),
    'nat': ('nat',),
    'string': ('string',),
    'var_nat': ('var','nat'),
    'var_string': ('var','string'),
    'nat_string': ('nat','string'),
    'all': ('var','nat','string'),
}

def block(variant):
    parts = VARIANTS[variant]
    arms = ''
    if 'var' in parts: arms += VAR
    if 'nat' in parts: arms += NAT
    if 'string' in parts: arms += STRING
    return '''    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        // V92 isolated leaf fast-path tournament arm: %s
        match *self.ctx.read_expr_ref(e) {
%s            _ => {}
        }
        if e.num_loose_bvars() == 0 && env.lsub().is_none() {
''' % (variant, arms)

def transform(source, variant):
    assert variant in VARIANTS
    assert source.count(OLD) == 1, 'evaluation entry anchor mismatch'
    new = block(variant)
    result = source.replace(OLD, new)
    assert result.replace(new, OLD) == source
    return result

def prepare(variant):
    v.ROOT.mkdir(parents=True, exist_ok=True)
    v.OUT.mkdir(parents=True, exist_ok=True)
    assert not (v.ROOT/'control').exists(), 'Use a fresh V92_ROOT'
    v.call(['git','clone','-q','https://github.com/metalogiclabs/mathgraph-lean-kernel',str(v.ROOT/'control')])
    v.call(['git','-C',str(v.ROOT/'control'),'checkout','-q',v.BASE])
    assert v.capture(['git','-C',str(v.ROOT/'control'),'rev-parse','HEAD']).stdout.decode().strip()==v.BASE
    shutil.copytree(v.ROOT/'control',v.ROOT/'candidate',ignore=shutil.ignore_patterns('.git','target'))
    old=(v.ROOT/'control/src/eval.rs').read_bytes()
    assert v.blob(old)==BASE_EVAL
    new=transform(old.decode(), variant).encode()
    (v.ROOT/'candidate/src/eval.rs').write_bytes(new)
    assert old != new
    for path in ['src/util.rs','src/tests.rs','Cargo.lock']:
        assert (v.ROOT/'control'/path).read_bytes()==(v.ROOT/'candidate'/path).read_bytes()
    (v.OUT/'production.patch').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='control/src/eval.rs',tofile='candidate/src/eval.rs')))
    v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(v.ROOT/'arena')])
    v.call(['git','-C',str(v.ROOT/'arena'),'checkout','-q',v.ARENA])
    assert v.capture(['git','-C',str(v.ROOT/'arena'),'rev-parse','HEAD']).stdout.decode().strip()==v.ARENA
    (v.ROOT/'config.json').write_text(json.dumps(v.CONFIG)+'\n')
    v.save({'base':v.BASE,'arena':v.ARENA,'source_commit':os.environ.get('GITHUB_SHA'),'variant':variant,
            'change':'direct eval leaf fast path subset before general cache dispatch',
            'source_hashes':{arm:{p:v.blob((v.ROOT/arm/p).read_bytes()) for p in ['src/eval.rs','src/util.rs','src/tests.rs','Cargo.lock']} for arm in ['control','candidate']}},'source.json')
    for corpus in ['init-prelude','cedar','mathlib']:
        v.call(['./lka.py','build-test',corpus],cwd=v.ROOT/'arena',log='build-'+corpus+'.log')
    v.save({c:v.sha_file(v.ROOT/'arena/_build/tests'/(c+'.ndjson')) for c in ['init-prelude','cedar','mathlib']},'inputs.json')

def run(variant):
    v.OUT.mkdir(parents=True,exist_ok=True)
    summary={'schema':1,'status':'IN_PROGRESS','release_promoted':False,'variant':variant,'base':v.BASE,'arena':v.ARENA,
             'build':'native-fresh-pgo-4threads','corpora':{}}
    v.save(summary)
    try:
        prepare(variant)
        v.qualification()
        binaries={arm:v.build_pgo(arm) for arm in ['control','candidate']}
        assert binaries['control']['sha256'] != binaries['candidate']['sha256']
        summary['binaries']=binaries
        v.save(summary)
        v.measure(binaries,summary)
        summary['status']='COMPLETE'
        summary['decision']='TOURNAMENT_RESULT__NO_RELEASE_PROMOTION'
    except BaseException as exc:
        summary['status']='FAILED'; summary['error']=repr(exc); v.save(summary); raise
    v.save(summary)
    print('V92_VARIANT='+variant,flush=True)
    for corpus in ['std','cedar','mathlib']:
        print('V92_%s_%s_DELTA_PERCENT=%.4f'%(variant.upper(),corpus.upper(),summary['corpora'][corpus]['delta_percent']),flush=True)
    print('V92_%s_GEOMEAN_DELTA_PERCENT=%.4f'%(variant.upper(),summary['geomean_delta_percent']),flush=True)
    print('V92_%s_TIMING_DECISION=%s'%(variant.upper(),summary['timing_decision']),flush=True)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        for name in VARIANTS:
            t=transform(OLD,name)
            assert t.replace(block(name),OLD)==OLD
            assert ('Expr::Var' in t)==('var' in VARIANTS[name])
            assert ('Expr::NatLit' in t)==('nat' in VARIANTS[name])
            assert ('Expr::StringLit' in t)==('string' in VARIANTS[name])
        print('V92_TOURNAMENT_PATCH_SELF_TEST=PASS',flush=True)
    else:
        if len(sys.argv)!=2 or sys.argv[1] not in VARIANTS:
            raise SystemExit('usage: eval_leaf_tournament_v92.py VARIANT')
        variant=sys.argv[1]
        v.ROOT=Path(os.environ.get('V92_ROOT','/tmp/v92-'+variant))
        v.OUT=v.ROOT/'out'
        run(variant)
