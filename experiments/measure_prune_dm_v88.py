#!/usr/bin/env python3
"""Exact full-corpus replay and balanced wall-time comparison against frozen incumbent."""
import hashlib,json,math,statistics,subprocess,sys,time
from pathlib import Path
r=Path(sys.argv[1]); out=r/'out'; cfg=r/'config.json'
results={'base':'08ddb26718c86213262943ca19ae8cf1b03fa922','arena':'91f376e4baacf2df0c478e7173bccb2a6adac5c5','build':'native-fresh-pgo-4threads','status':'IN_PROGRESS','corpora':{}}
def save():
    (out/'results.json').write_text(json.dumps(results,indent=2))
def run(arm,corpus,data,tag):
    start=time.perf_counter()
    p=subprocess.run([str(r/f'{arm}-checker'),str(cfg)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200)
    t=time.perf_counter()-start
    (out/f'{corpus}.{tag}.stdout').write_bytes(p.stdout)
    (out/f'{corpus}.{tag}.stderr').write_bytes(p.stderr)
    return {'rc':p.returncode,'seconds':t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
try:
    deltas=[]
    for corpus in ('std','cedar','mathlib'):
        data=(r/'arena'/'_build/tests'/f'{corpus}.ndjson').read_bytes()
        assert data,corpus
        entry={'input_sha256':hashlib.sha256(data).hexdigest(),'runs':[]}
        results['corpora'][corpus]=entry;save()
        ref=run('control',corpus,data,'reference')
        cand=run('candidate',corpus,data,'candidate')
        entry.update(reference=ref,candidate=cand);save()
        assert ref['rc']==cand['rc']==0,(corpus,ref,cand)
        assert ref['stdout_sha256']==cand['stdout_sha256'],corpus
        assert ref['stderr_sha256']==cand['stderr_sha256'],corpus
        entry['exact_replay']='PASS';save()
        print(f'V88_{corpus.upper()}_EXACT_REPLAY=PASS',flush=True)
        for i in range(5):
            for arm in (('control','candidate') if i%2==0 else ('candidate','control')):
                row=run(arm,corpus,data,f'{arm}.{i}')
                entry['runs'].append({'pass':i,'arm':arm,**row});save()
                assert row['rc']==0,(corpus,arm,i)
                assert row['stdout_sha256']==ref['stdout_sha256'],(corpus,arm,i)
                assert row['stderr_sha256']==ref['stderr_sha256'],(corpus,arm,i)
        a=statistics.median(x['seconds'] for x in entry['runs'] if x['arm']=='control')
        b=statistics.median(x['seconds'] for x in entry['runs'] if x['arm']=='candidate')
        delta=100*(b/a-1)
        entry.update(control_median=a,candidate_median=b,delta_percent=delta)
        deltas.append(delta);save()
        print(f'V88_{corpus.upper()}_CONTROL_MEDIAN={a:.4f}',flush=True)
        print(f'V88_{corpus.upper()}_CANDIDATE_MEDIAN={b:.4f}',flush=True)
        print(f'V88_{corpus.upper()}_DELTA_PERCENT={delta:.4f}',flush=True)
    geo=100*(math.prod(1+d/100 for d in deltas)**(1/len(deltas))-1)
    results['geomean_delta_percent']=geo
    results['status']='COMPLETE'
    results['decision']='REPEAT_AND_ABLATE' if geo<=-1 and max(deltas)<=0 else 'REJECT_OR_INCONCLUSIVE'
    print('V88_GEOMEAN_DELTA_PERCENT=%.4f'%geo,flush=True)
    print('DECISION='+results['decision']+'__NO_RELEASE_PROMOTION',flush=True)
except BaseException as e:
    results['status']='FAILED';results['error']=repr(e);save();raise
save()
