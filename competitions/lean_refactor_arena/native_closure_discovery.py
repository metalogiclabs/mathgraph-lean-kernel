#!/usr/bin/env python3
"""Map native unsolved-goal diagnostics to a conservative local rfl proposal.

The rewrite grammar is programmer supplied. Native locations select scope; no
mathematical theorem name, observer or replacement proof is manually specified.
The error-to-source mapping is checked against an actual `:= by` line, otherwise
acquisition fails closed. Every repair is an unverified candidate.
"""
import argparse,hashlib,json,re
from pathlib import Path

def digest(s):return hashlib.sha256(s.encode()).hexdigest()

def repair(row,log,source_start):
    proof=row['proof'];lines=proof.splitlines()
    matches=re.findall(r'\.lean:(\d+):\d+: error: unsolved goals',log)
    if len(matches)!=1:return None
    scope=int(matches[0])-source_start
    if not 1<=scope<len(lines) or not lines[scope-1].rstrip().endswith(':= by'):return None
    first=scope
    while first<len(lines) and not lines[first].strip():first+=1
    if first==len(lines):return None
    indent=len(lines[first])-len(lines[first].lstrip())
    if indent<1:return None
    end=first+1
    while end<len(lines):
        line=lines[end]
        if line.strip() and len(line)-len(line.lstrip())<indent:break
        end+=1
    insertion=end
    while insertion>first and not lines[insertion-1].strip():insertion-=1
    lines.insert(insertion,' '*indent+'all_goals rfl')
    candidate='\n'.join(lines)+'\n'
    if candidate.split(':= by',1)[0]!=proof.split(':= by',1)[0]:raise ValueError('statement mutation')
    sha=digest(candidate)
    return dict(name=row['name'],proof=candidate,label='native_definitional_closure_'+sha[:12],
      operator='native_definitional_closure',rule_version='source-native-closure-v3',
      proof_sha256=sha,parent_sha256=digest(proof),status='CANDIDATE_UNVERIFIED',
      discovered=dict(proof_scope_line=scope,inserted_after_proof_line=insertion,
        native_error_line=int(matches[0]),source_start=source_start,
        parent_label=row.get('label'),parent_operator=row.get('operator'),
        native_error_sha256=digest(log)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bank',required=True);ap.add_argument('--results',required=True);ap.add_argument('--diagnostics',required=True);ap.add_argument('--benchmark',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    rows=[json.loads(x) for x in Path(a.bank).read_text().splitlines()]
    results=[json.loads(x) for x in Path(a.results).read_text().splitlines()]
    bench={r['name']:r for r in map(json.loads,Path(a.benchmark).read_text().splitlines())}
    output=[]
    for row in rows:
        result=next(r for r in results if (r['name'],r['candidate_label'])==(row['name'],row['label']))
        if row['operator']=='control' or result.get('compiled'):
            output.append(row);continue
        errors=[e for p in result.get('per_version',[]) for e in p.get('errors',[])]
        if errors!=['unsolved goals']:continue
        if result.get('proof_sha256')!=digest(row['proof']):raise ValueError('native parent hash mismatch')
        log=(Path(a.diagnostics)/(row['label']+'.lean.log')).read_text()
        candidate=repair(row,log,bench[row['name']]['start_line'])
        if candidate:output.append(candidate)
    Path(a.out).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output))
    print(json.dumps(dict(rows=len(output),bank_sha256=digest(Path(a.out).read_text()))))
if __name__=='__main__':main()
