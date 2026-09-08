#!/usr/bin/env python3
"""V91: bypass general evaluation dispatch for variables and literals."""
import difflib
import json
import os
import shutil
import sys
from pathlib import Path
import profile_v89 as v
import eval_raw_v90 as harness

BASE_EVAL = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
OLD = '''    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        if e.num_loose_bvars() == 0 && env.lsub().is_none() {
'''
NEW = '''    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        // Leaf values need neither environment projection nor cache dispatch.
        match *self.ctx.read_expr_ref(e) {
            Expr::Var { dbj_idx, .. } => {
                let v = env.lookup(dbj_idx).expect("eval: loose bvar");
                return self.force_thunk(depth, v);
            }
            Expr::NatLit { ptr, .. } => return value::mk_natlit(self.arena, ptr),
            Expr::StringLit { ptr, .. } => return value::mk_strlit(self.arena, ptr),
            _ => {}
        }
        if e.num_loose_bvars() == 0 && env.lsub().is_none() {
'''

def transform(source):
    assert source.count(OLD) == 1, 'evaluation entry anchor mismatch'
    result = source.replace(OLD, NEW)
    assert result.replace(NEW, OLD) == source
    return result

def prepare():
    v.ROOT.mkdir(parents=True, exist_ok=True)
    v.OUT.mkdir(parents=True, exist_ok=True)
    assert not (v.ROOT/'control').exists(), 'Use a fresh V91_ROOT'
    v.call(['git','clone','-q','https://github.com/metalogiclabs/mathgraph-lean-kernel',str(v.ROOT/'control')])
    v.call(['git','-C',str(v.ROOT/'control'),'checkout','-q',v.BASE])
    assert v.capture(['git','-C',str(v.ROOT/'control'),'rev-parse','HEAD']).stdout.decode().strip()==v.BASE
    shutil.copytree(v.ROOT/'control',v.ROOT/'candidate',ignore=shutil.ignore_patterns('.git','target'))
    old=(v.ROOT/'control/src/eval.rs').read_bytes()
    assert v.blob(old)==BASE_EVAL
    new=transform(old.decode()).encode()
    (v.ROOT/'candidate/src/eval.rs').write_bytes(new)
    assert old!=new
    for path in ['src/util.rs','src/tests.rs','Cargo.lock']:
        assert (v.ROOT/'control'/path).read_bytes()==(v.ROOT/'candidate'/path).read_bytes()
    (v.OUT/'production.patch').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='control/src/eval.rs',tofile='candidate/src/eval.rs')))
    v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(v.ROOT/'arena')])
    v.call(['git','-C',str(v.ROOT/'arena'),'checkout','-q',v.ARENA])
    assert v.capture(['git','-C',str(v.ROOT/'arena'),'rev-parse','HEAD']).stdout.decode().strip()==v.ARENA
    (v.ROOT/'config.json').write_text(json.dumps(v.CONFIG)+'\n')
    v.save({'base':v.BASE,'arena':v.ARENA,'source_commit':os.environ.get('GITHUB_SHA'),
            'change':'direct variable and literal evaluation before general cache dispatch',
            'source_hashes':{arm:{p:v.blob((v.ROOT/arm/p).read_bytes()) for p in ['src/eval.rs','src/util.rs','src/tests.rs','Cargo.lock']} for arm in ['control','candidate']}},'source.json')
    for corpus in ['init-prelude','cedar','mathlib']:
        v.call(['./lka.py','build-test',corpus],cwd=v.ROOT/'arena',log='build-'+corpus+'.log')
    v.save({c:v.sha_file(v.ROOT/'arena/_build/tests'/(c+'.ndjson')) for c in ['init-prelude','cedar','mathlib']},'inputs.json')

if __name__=='__main__':
    if '--self-test' in sys.argv:
        assert transform(OLD).replace(NEW,OLD)==OLD
        assert transform(OLD).count('Leaf values')==1
        print('V91_PATCH_SELF_TEST=PASS',flush=True)
    else:
        v.ROOT=Path(os.environ.get('V91_ROOT','/tmp/v91'))
        v.OUT=v.ROOT/'out'
        harness.prepare=prepare
        harness.run()
