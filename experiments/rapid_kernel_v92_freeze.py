#!/usr/bin/env python3
"""Freeze actual corpus bytes before the v92 search; never guess a source hash."""
import json
import os
import shutil
import sys
from pathlib import Path
import rapid_kernel_v92 as r

ROOT = r.ROOT
FIXTURES = ROOT / 'fixtures'
MANIFEST = FIXTURES / 'manifest.json'
CORPORA = ('init-prelude', 'cedar', 'mathlib')

def freeze():
    r.v.ROOT = ROOT
    r.v.OUT = r.OUT
    ROOT.mkdir(parents=True, exist_ok=True)
    r.OUT.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    arena = ROOT / 'arena'
    if not (arena / '.git').exists():
        r.v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(arena)])
    r.v.call(['git','-C',str(arena),'checkout','-q',r.v.ARENA])
    assert r.v.capture(['git','-C',str(arena),'rev-parse','HEAD']).stdout.decode().strip() == r.v.ARENA
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        assert manifest['arena'] == r.v.ARENA
        assert set(manifest['inputs']) == set(CORPORA)
        for corpus, sha in manifest['inputs'].items():
            p = FIXTURES / (corpus + '.ndjson')
            assert p.is_file() and r.v.sha_file(p) == sha, 'Frozen fixture corrupted: ' + corpus
        print('V92_FROZEN_INPUTS=RESTORED', flush=True)
    else:
        inputs = {}
        for corpus in CORPORA:
            r.v.call(['./lka.py','build-test',corpus],cwd=arena,log='build-'+corpus+'.log',timeout=3600)
            p = arena / '_build/tests' / (corpus + '.ndjson')
            assert p.is_file() and p.stat().st_size > 0
            frozen = FIXTURES / p.name
            shutil.copy2(p, frozen)
            inputs[corpus] = r.v.sha_file(frozen)
        manifest = {'schema':1,'arena':r.v.ARENA,'inputs':inputs,
                    'sizes':{c:(FIXTURES/(c+'.ndjson')).stat().st_size for c in CORPORA},
                    'source_test_hashes':{c:r.v.sha_file(arena/'tests'/(c+'.yaml')) for c in CORPORA}}
        tmp = FIXTURES / 'manifest.json.tmp'
        tmp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        os.replace(tmp,MANIFEST)
        print('V92_FROZEN_INPUTS=CREATED', flush=True)
    # The search reads only these archived bytes. A later build cannot silently replace them.
    dest = arena / '_build/tests'
    dest.mkdir(parents=True,exist_ok=True)
    for corpus, sha in manifest['inputs'].items():
        src = FIXTURES / (corpus+'.ndjson')
        dst = dest / src.name
        if not dst.exists() or r.v.sha_file(dst) != sha:
            shutil.copy2(src,dst)
        assert r.v.sha_file(dst) == sha
    r.EXPECTED = dict(manifest['inputs'])
    r.save(manifest,'frozen-inputs.json')
    print('V92_INPUT_MANIFEST=' + json.dumps(manifest['inputs'],sort_keys=True),flush=True)

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        assert set(CORPORA)==set(r.EXPECTED)
        assert len(set(CORPORA))==3
        print('V92_FREEZE_SELF_TEST=PASS',flush=True)
    else:
        freeze()
        r.main()
