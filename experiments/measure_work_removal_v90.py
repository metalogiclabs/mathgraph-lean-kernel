#!/usr/bin/env python3
"""Measure a frozen candidate against the incumbent; never silently promote."""
import hashlib, json, math, statistics, subprocess, sys, time
from pathlib import Path

root = Path(sys.argv[1]); out = root/'out'; cfg = root/'config.json'
corpora = {'std':'init-prelude', 'cedar':'cedar', 'mathlib':'mathlib'}
result = {'schema':1, 'base':'08ddb26718c86213262943ca19ae8cf1b03fa922',
          'candidate_upstream':'ceaabb593e830dd318bfefd1675be3142fad8eb7',
          'arena':'91f376e4baacf2df0c478e7173bccb2a6adac5c5',
          'build':'native-fresh-pgo-4threads', 'status':'IN_PROGRESS',
          'corpora':{}, 'release_promoted':False}

def save():
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')

def run(arm, data):
    start = time.perf_counter()
    p = subprocess.run([str(root/(arm+'-checker')),str(cfg)],input=data,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200)
    return {'rc':p.returncode,'seconds':time.perf_counter()-start,
            'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}

def verify(row, expected, name):
    if row['rc'] != 0 or (row['stdout_sha256'],row['stderr_sha256']) != expected:
        raise ValueError('semantic replay mismatch: '+name)

try:
    for name, export in corpora.items():
        data = (root/'arena'/'_build/tests'/(export+'.ndjson')).read_bytes()
        if not data: raise ValueError('empty corpus: '+name)
        e = {'input_sha256':hashlib.sha256(data).hexdigest(),'input_bytes':len(data),'runs':[]}
        result['corpora'][name]=e; save()
        ref=run('control',data); cand=run('candidate',data)
        e.update(reference=ref,candidate=cand); save()
        expected=(ref['stdout_sha256'],ref['stderr_sha256'])
        verify(ref,expected,name+' control'); verify(cand,expected,name+' candidate')
        e['exact_replay']='PASS'; save()
        print('V90_'+name.upper()+'_EXACT_REPLAY=PASS',flush=True)
        for i in range(5):
            order=('control','candidate') if i%2==0 else ('candidate','control')
            for arm in order:
                row=run(arm,data); verify(row,expected,name+' '+arm)
                e['runs'].append({'pass':i,'arm':arm,**row}); save()
        a=statistics.median(r['seconds'] for r in e['runs'] if r['arm']=='control')
        b=statistics.median(r['seconds'] for r in e['runs'] if r['arm']=='candidate')
        e.update(control_median=a,candidate_median=b,delta_percent=100*(b/a-1)); save()
        print('V90_'+name.upper()+'_CONTROL_MEDIAN=%.4f'%a,flush=True)
        print('V90_'+name.upper()+'_CANDIDATE_MEDIAN=%.4f'%b,flush=True)
        print('V90_'+name.upper()+'_DELTA_PERCENT=%.4f'%e['delta_percent'],flush=True)
    ds=[result['corpora'][n]['delta_percent'] for n in ('cedar','mathlib')]
    geo=100*(math.prod(1+d/100 for d in ds)**.5-1)
    result['large_corpus_geomean_delta_percent']=geo
    result['status']='COMPLETE'
    result['decision']='REPEAT_AND_ABLATE' if all(d<=-1 for d in ds) else 'REJECT_OR_INCONCLUSIVE'
    result['next']='Independent repeat and release qualification' if result['decision']=='REPEAT_AND_ABLATE' else 'Retain incumbent; seek a different measured obstruction'
    save()
    print('V90_LARGE_CORPUS_GEOMEAN_PERCENT=%.4f'%geo,flush=True)
    print('V90_DECISION='+result['decision']+'__NO_RELEASE_PROMOTION',flush=True)
except BaseException as exc:
    result['status']='FAILED';result['error']=repr(exc);save();raise
