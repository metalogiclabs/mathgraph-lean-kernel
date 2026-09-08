#!/usr/bin/env python3
"""V93: full-corpus tournament. Search results never promote a checker."""
import json
import math
import os
import shutil
import statistics
import sys
from pathlib import Path
import profile_v89 as v
import rapid_kernel_v92 as r

ROOT = Path(os.environ.get('V93_ROOT', '/tmp/v93'))
OUT = ROOT / 'out'
CORPORA = ('init-prelude', 'cedar', 'mathlib')
# Historical evidence, not a recipe for regenerating byte-identical inputs.
HISTORICAL_V92 = {'init-prelude':'fc440bd35aa4ecb244836eef0c2e31c578ac4460f42665f4e8305cbc2cd2104d',
                  'cedar':'577288c46213303b2e9f948d4014a4f622b496d3bbad19476e81f3ff82eb08a6',
                  'mathlib':'ca2ec20fd063b61e71867b2975c81bd989af9f879b4886b8f08cd23c767a47bb'}
SOURCE_TEST_HASHES = {'cedar':'4e5c4a350c280cf082a10d46b473052dd9a6e08a926a4080e33f20b81c27e10a',
                      'init-prelude':'4a962d8b3e0e9b1931d07e329c5478310a0852cc44955ac1b72686755f25e5f0',
                      'mathlib':'9096bfbf183366d967c60d8c58120654715a63f27bf90b62912607b8c01c25cf'}
FROZEN = dict(HISTORICAL_V92)
VARIANTS = {x[0]:x for x in r.VARIANTS}
COMMON = '-C target-cpu=native -C debuginfo=1 -C force-frame-pointers=yes'

def save(obj, name='summary.json'):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')

def select_fixtures(manifest):
    assert manifest['arena'] == v.ARENA
    assert manifest['source_test_hashes'] == SOURCE_TEST_HASHES
    inputs = dict(manifest['inputs'])
    assert set(inputs) == set(CORPORA)
    assert all(isinstance(h, str) and len(h) == 64 and all(c in '0123456789abcdef' for c in h) for h in inputs.values())
    identity = {'arena':v.ARENA, 'inputs':inputs, 'source_test_hashes':SOURCE_TEST_HASHES}
    fixture_id = v.sha(json.dumps(identity, sort_keys=True, separators=(',',':')).encode())
    return inputs, fixture_id

def setup():
    global FROZEN
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    v.ROOT = r.ROOT = ROOT
    v.OUT = r.OUT = OUT
    # Rebuilding can produce different bytes. Preserve the historical hashes,
    # but give the newly observed, archived bytes their own fixture identity.
    from rapid_kernel_v92_freeze import freeze
    freeze()
    fixtures = ROOT/'fixtures'
    manifest = json.loads((fixtures/'manifest.json').read_text())
    FROZEN, fixture_id = select_fixtures(manifest)
    r.EXPECTED = dict(FROZEN)
    arena = ROOT/'arena'
    if not (arena/'.git').exists():
        v.call(['git','clone','-q','https://github.com/leanprover/lean-kernel-arena',str(arena)])
    v.call(['git','-C',str(arena),'checkout','-q',v.ARENA])
    assert v.capture(['git','-C',str(arena),'rev-parse','HEAD']).stdout.decode().strip() == v.ARENA
    dest = arena/'_build/tests'
    dest.mkdir(parents=True,exist_ok=True)
    for corpus,sha in FROZEN.items():
        src = fixtures/(corpus+'.ndjson')
        assert src.is_file() and v.sha_file(src) == sha
        shutil.copy2(src,dest/src.name)
        assert v.sha_file(dest/src.name) == sha
    r.setup()
    source = {'base':v.BASE,'arena':v.ARENA,'inputs':FROZEN,
              'historical_v92_inputs':HISTORICAL_V92,'fixture_set_id':fixture_id,
              'changed_from_v92':FROZEN != HISTORICAL_V92,
              'source_test_hashes':SOURCE_TEST_HASHES,
              'source_commit':os.environ.get('GITHUB_SHA'),
              'variants':list(VARIANTS),'build':'shared-baseline-PGO-then-fresh-finalist-PGO',
              'screen':'complete frozen corpora; no prefixes'}
    save(source,'source.json')
    print('V93_FROZEN_INPUTS=PASS',flush=True)
    print('V93_FIXTURE_SET_ID='+fixture_id,flush=True)
    print('V93_CHANGED_FROM_V92='+str(FROZEN != HISTORICAL_V92).lower(),flush=True)

def build_search():
    # Train once on the frozen prelude, then use the same profile for every arm.
    control = v.build_pgo('control')
    profile = ROOT/'pgo-control/merged.profdata'
    flags = COMMON+' -C profile-use='+str(profile)
    binaries = {'control':dict(control,source_hashes=r.install(VARIANTS['control']),search_profile_sha256=v.sha_file(profile))}
    (ROOT/'binaries').mkdir(exist_ok=True)
    for name,variant in VARIANTS.items():
        if name == 'control': continue
        hashes = r.install(variant)
        env = dict(os.environ,CARGO_TARGET_DIR=str(ROOT/'target-search'),CARGO_INCREMENTAL='0',RUSTFLAGS=flags)
        v.call(['cargo','build','--release','--locked','-q'],cwd=ROOT/'work',env=env,log=name+'.build.log',timeout=3600)
        binary = ROOT/'binaries'/name
        shutil.copy2(ROOT/'target-search/release/sokonanoda',binary)
        binaries[name] = {'path':str(binary),'sha256':v.sha_file(binary),'source_hashes':hashes,
                          'flags':flags,'search_profile_sha256':v.sha_file(profile)}
        assert binaries[name]['sha256'] != control['sha256']
    assert len({x['sha256'] for x in binaries.values()}) == len(binaries), 'Duplicate tournament binaries'
    return binaries

def score(rows, names):
    result = {}
    for name in names:
        by_corpus = {}
        for corpus in CORPORA:
            xs = [x['ratio'] for x in rows if x['arm']==name and x['corpus']==corpus]
            assert xs
            by_corpus[corpus] = {'delta_percent':100*(statistics.median(xs)-1),'ratios':xs}
        ds = [by_corpus[c]['delta_percent'] for c in CORPORA]
        result[name] = {'corpora':by_corpus,
                        'geomean_delta_percent':100*(math.prod(1+d/100 for d in ds)**(1/len(ds))-1),
                        'max_regression_percent':max(ds)}
    return result

def race(binaries, names, phase, passes, summary):
    rows=[]
    for corpus in CORPORA:
        for i in range(passes):
            order = list(names) if i%2==0 else list(reversed(names))
            before = v.run_binary(binaries['control']['path'],corpus,f'{phase}.{corpus}.{i}.before')
            assert before['rc']==0
            reference = (before['stdout_sha256'],before['stderr_sha256'])
            pending=[]
            for name in order:
                row = v.run_binary(binaries[name]['path'],corpus,f'{phase}.{corpus}.{i}.{name}')
                assert row['rc']==0 and (row['stdout_sha256'],row['stderr_sha256'])==reference, 'Replay mismatch: '+name+'/'+corpus
                pending.append((name,row))
            after = v.run_binary(binaries['control']['path'],corpus,f'{phase}.{corpus}.{i}.after')
            assert after['rc']==0 and (after['stdout_sha256'],after['stderr_sha256'])==reference
            baseline = statistics.median([before['seconds'],after['seconds']])
            drift = abs(after['seconds']/before['seconds']-1)*100
            assert drift <= 5, 'Control drift exceeds 5%: '+corpus
            for name,row in pending:
                rows.append({'arm':name,'corpus':corpus,'pass':i,'ratio':row['seconds']/baseline,
                             'baseline_seconds':baseline,'control_before':before,'control_after':after,'candidate':row})
            summary[phase]={'rows':rows,'scores':score(rows,[n for n in names if all(any(x['arm']==n and x['corpus']==c for x in rows) for c in CORPORA)])}
            save(summary)
        print('V93_'+phase.upper()+'_'+corpus.upper()+'=COMPLETE',flush=True)
    return score(rows,names),rows

def qualify(winner,summary):
    # Only the finalist pays for independent PGO and complete unit tests.
    shutil.rmtree(ROOT/'candidate',ignore_errors=True)
    shutil.copytree(ROOT/'control',ROOT/'candidate',ignore=shutil.ignore_patterns('.git','target'))
    e,u = r.source_pair((ROOT/'control/src/eval.rs').read_text(),(ROOT/'control/src/util.rs').read_text(),VARIANTS[winner])
    (ROOT/'candidate/src/eval.rs').write_text(e)
    (ROOT/'candidate/src/util.rs').write_text(u)
    v.qualification()
    summary['qualification']=json.loads((OUT/'qualification.json').read_text())
    # The baseline was already trained independently in build_search; do not rebuild it.
    binaries = {'control':summary['binaries']['control'],'candidate':v.build_pgo('candidate')}
    summary['qualification_binaries']=binaries
    save(summary)
    scores,rows = race(binaries,['candidate'],'qualification_race',3,summary)
    result = scores['candidate']
    summary['qualification_score']=result
    good = result['geomean_delta_percent'] <= -2 and result['max_regression_percent'] <= 1
    round_gains=[]
    for i in range(3):
        ds=[next(x['ratio'] for x in rows if x['pass']==i and x['corpus']==c) for c in CORPORA]
        round_gains.append(math.prod(ds)**(1/3)-1)
    good = good and sum(x<0 for x in round_gains)>=2
    summary['qualification_round_geomeans']=round_gains
    summary['decision']='QUALIFIED_GAIN_CANDIDATE__RELEASE_BLOCKED_KNOWN_FIXTURES' if good else 'REJECT_OR_INCONCLUSIVE'
    summary['release_promoted']=False
    save(summary)
    print('V93_QUALIFICATION_GEOMEAN_DELTA_PERCENT=%.4f'%result['geomean_delta_percent'],flush=True)

def main():
    summary={'schema':1,'status':'IN_PROGRESS','decision':'NOT_YET_MEASURED','release_promoted':False}
    save(summary)
    try:
        setup()
        binaries=build_search()
        summary['binaries']=binaries
        save(summary)
        names=[n for n in VARIANTS if n!='control']
        first,_=race(binaries,names,'round1',1,summary)
        ranked=sorted(names,key=lambda n:first[n]['geomean_delta_percent'])
        finalists=[n for n in ranked if first[n]['geomean_delta_percent'] <= -0.5 and first[n]['max_regression_percent']<=2.5][:3]
        summary['ranking']=ranked
        summary['finalists']=finalists
        save(summary)
        if finalists:
            second,_=race(binaries,finalists,'round2',1,summary)
            candidates=[n for n in finalists if second[n]['geomean_delta_percent']<0 and
                        first[n]['geomean_delta_percent']<0 and second[n]['max_regression_percent']<=1.5]
            candidates.sort(key=lambda n:second[n]['geomean_delta_percent'])
            summary['nominees']=candidates
            save(summary)
            if candidates and second[candidates[0]]['geomean_delta_percent']<=-1.5:
                summary['winner']=candidates[0]
                save(summary)
                qualify(candidates[0],summary)
            else:
                summary['decision']='NO_REPRODUCIBLE_NOMINEE__NO_FULL_QUALIFICATION'
        else:
            summary['decision']='NO_FULL_CORPUS_SCREENING_WINNER'
        summary['status']='COMPLETE'
    except BaseException as exc:
        summary['status']='FAILED';summary['error']=repr(exc)
        save(summary)
        raise
    save(summary)
    print('V93_DECISION='+summary['decision'],flush=True)
    print('V93_RELEASE_PROMOTED=false',flush=True)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        assert len(VARIANTS)==8 and len(set(VARIANTS))==8
        assert r.transform(r.leaf.OLD,True,True).replace('        // Direct evaluation of selected leaves.','        // Leaf values need neither environment projection nor cache dispatch.')==r.leaf.NEW
        sample=[{'arm':'a','corpus':c,'ratio':0.9} for c in CORPORA]
        result=score(sample,['a'])['a']
        assert abs(result['geomean_delta_percent']+10)<1e-9
        assert result['max_regression_percent']<0
        old_id=select_fixtures({'arena':v.ARENA,'inputs':HISTORICAL_V92,'source_test_hashes':SOURCE_TEST_HASHES})[1]
        changed=dict(HISTORICAL_V92);changed['cedar']='75f512b4ab68319cdfaca5d53c6bff25a95a702567bbf293060df735498aaa24'
        assert select_fixtures({'arena':v.ARENA,'inputs':changed,'source_test_hashes':SOURCE_TEST_HASHES})[1]!=old_id
        print('V93_TOURNAMENT_SELF_TEST=PASS',flush=True)
    else:
        main()
