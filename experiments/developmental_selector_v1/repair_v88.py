#!/usr/bin/env python3
"""Execute only the frozen controller's exact, source-guarded harness repair."""
import argparse, hashlib, json, ast
from pathlib import Path
from controller import digest, safe_decision

OLD_BLOB='30b98f1a90b89ac222f96d2498161b5eb86ec05b'
OLD="        data=(r/'arena'/'_build/tests'/f'{corpus}.ndjson').read_bytes()\n"
NEW="        filename={'std':'init-prelude','cedar':'cedar','mathlib':'mathlib'}[corpus]\n        data=(r/'arena'/'_build/tests'/f'{filename}.ndjson').read_bytes()\n"
SOURCE_COMMIT='5271aa0fe53fe3243d999ead6d49bde481e2c6b2'

def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def transform(source):
    if source.count(OLD)!=1:
        raise ValueError('unexpected corpus path statement')
    result=source.replace(OLD,NEW,1)
    ast.parse(result)
    assert result.replace(NEW,OLD,1)==source
    return result

def paths(root):
    result=[]
    for name in ('init-prelude','cedar','mathlib'):
        p=Path(root)/'arena'/'_build'/'tests'/(name+'.ndjson')
        if not p.is_file() or p.stat().st_size==0:
            raise FileNotFoundError(p)
        result.append(p)
    return result

def execute(source, policy_file, decision_file, check=False):
    policy=json.loads(Path(policy_file).read_text())
    decision=json.loads(Path(decision_file).read_text())
    if digest(policy)!=decision['policy_sha256']:
        raise ValueError('frozen policy mismatch')
    if safe_decision(policy,decision['state'])!='REPAIR' or decision['action']!='REPAIR':
        raise ValueError('repair not authorized by controller')
    if decision['source_commit']!=SOURCE_COMMIT or decision['source_blob']!=OLD_BLOB:
        raise ValueError('source provenance mismatch')
    history=json.loads(Path(policy_file).with_name('history.json').read_text())
    current=next(r for r in history['heldout'] if r['id']=='v88')
    if current['state']!=decision['state'] or current['outcome']!='pending':
        raise ValueError('stale or changed continuation')
    p=Path(source);raw=p.read_bytes()
    if blob(raw)!=OLD_BLOB:
        raise ValueError('frozen measurement source mismatch')
    result=transform(raw.decode())
    if not check:
        p.write_text(result)
    return blob(result.encode())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path)
    ap.add_argument('--policy',type=Path,default=Path(__file__).with_name('FROZEN_POLICY.json'))
    ap.add_argument('--decision',type=Path,default=Path(__file__).with_name('decision.json'))
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--corpus-root',type=Path)
    a=ap.parse_args()
    if a.corpus_root:
        found=paths(a.corpus_root)
        print('V88_CORPUS_MANIFEST=PASS')
        for p in found:
            print(p.name,p.stat().st_size)
    print('V88_MEASUREMENT_REPAIR_BLOB='+execute(a.source,a.policy,a.decision,a.check))
if __name__=='__main__':main()
