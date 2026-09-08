#!/usr/bin/env python3
"""V90: bypass repeated environment pruning on exact evaluation-cache hits."""
import difflib
import json
import os
import shutil
import sys
from pathlib import Path
import profile_v89 as v

BASE_EVAL = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
OLD = '''            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
'''
NEW = '''            // An exact environment hit needs no relevance projection.
            let raw_key = (env as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&raw_key) {
                return v;
            }
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                if raw_key != key {
                    self.tc_cache.open_eval_cache.insert(raw_key, v);
                }
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            if raw_key != key {
                self.tc_cache.open_eval_cache.insert(raw_key, v);
            }
            return v;
'''

def transform(source):
    assert source.count(OLD) == 1, 'evaluation cache anchor mismatch'
    result = source.replace(OLD, NEW)
    assert result.replace(NEW, OLD) == source
    return result

def prepare():
    v.ROOT.mkdir(parents=True, exist_ok=True)
    v.OUT.mkdir(parents=True, exist_ok=True)
    assert not (v.ROOT/'control').exists(), 'Use a fresh V90_ROOT'
    v.call(['git','clone','-q','https://github.com/metalogiclabs/mathgraph-lean-kernel',str(v.ROOT/'control')])
    v.call(['git','-C',str(v.ROOT/'control'),'checkout','-q',v.BASE])
    shutil.copytree(v.ROOT/'control',v.ROOT/'candidate',ignore=shutil.ignore_patterns('.git','target'))
    old=(v.ROOT/'control/src/eval.rs').read_bytes()
    assert v.blob(old)==BASE_EVAL
    new=transform(old.decode()).encode()
    (v.ROOT/'candidate/src/eval.rs').write_bytes(new)
    assert old!=new
    assert (v.ROOT/'control/src/util.rs').read_bytes()==(v.ROOT/'candidate/src/util.rs').read_bytes()
    assert (v.ROOT/'control/src/tests.rs').read_bytes()==(v.ROOT/'candidate/src/tests.rs').read_bytes()
    (v.OUT/'production.patch').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='control/src/eval.rs',tofile='candidate/src/eval.rs')))
    v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(v.ROOT/'arena')])
    v.call(['git','-C',str(v.ROOT/'arena'),'checkout','-q',v.ARENA])
    assert v.capture(['git','-C',str(v.ROOT/'arena'),'rev-parse','HEAD']).stdout.decode().strip()==v.ARENA
    (v.ROOT/'config.json').write_text(json.dumps(v.CONFIG)+'\n')
    v.save({'base':v.BASE,'arena':v.ARENA,'source_commit':os.environ.get('GITHUB_SHA'),
            'change':'raw evaluation-cache lookup and alias before relevance projection',
            'source_hashes':{arm:{p:v.blob((v.ROOT/arm/p).read_bytes()) for p in ['src/eval.rs','src/util.rs','src/tests.rs','Cargo.lock']} for arm in ['control','candidate']}},'source.json')
    for corpus in ['init-prelude','cedar','mathlib']:
        v.call(['./lka.py','build-test',corpus],cwd=v.ROOT/'arena',log='build-'+corpus+'.log')
    v.save({c:v.sha_file(v.ROOT/'arena/_build/tests'/(c+'.ndjson')) for c in ['init-prelude','cedar','mathlib']},'inputs.json')

def build(arm):
    target=v.ROOT/('target-'+arm)
    env=dict(os.environ,CARGO_TARGET_DIR=str(target),RUSTFLAGS='-C target-cpu=native')
    v.call(['cargo','build','--release','--locked','-q'],cwd=v.ROOT/arm,env=env,log=arm+'.build.log')
    binary=target/'release/sokonanoda'
    return {'path':str(binary),'sha256':v.sha_file(binary),'flags':env['RUSTFLAGS']}

def run():
    v.OUT.mkdir(parents=True,exist_ok=True)
    summary={'schema':1,'status':'IN_PROGRESS','release_promoted':False,'base':v.BASE,'arena':v.ARENA,'build':'native-release-4threads','corpora':{}}
    v.save(summary)
    try:
        prepare()
        binaries={arm:build(arm) for arm in ['control','candidate']}
        assert binaries['control']['sha256']!=binaries['candidate']['sha256']
        summary['binaries']=binaries
        v.save(summary)
        # Run the complete existing test suite, not merely a parser or controller self-test.
        v.qualification()
        summary['qualification']=json.loads((v.OUT/'qualification.json').read_text())
        v.measure(binaries,summary)
        summary['status']='COMPLETE'
        summary['decision']='DIAGNOSTIC_ONLY__NO_RELEASE_PROMOTION'
    except BaseException as exc:
        summary['status']='FAILED'
        summary['error']=repr(exc)
        v.save(summary)
        raise
    v.save(summary)
    print('V90_GEOMEAN_DELTA_PERCENT=%.4f'%summary['geomean_delta_percent'],flush=True)
    print('V90_TIMING_DECISION='+summary['timing_decision'],flush=True)
    print('V90_RELEASE_PROMOTED=false',flush=True)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        assert transform(OLD).replace(NEW,OLD)==OLD
        assert transform(OLD).count('raw_key')==5
        print('V90_PATCH_SELF_TEST=PASS')
    else:
        v.ROOT=Path(os.environ.get('V90_ROOT','/tmp/v90'))
        v.OUT=v.ROOT/'out'
        run()
