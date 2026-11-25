"""Frozen source-derived mutual-block controls. Case names never reach the checker."""
import argparse,copy,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--candidate-upstream',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
source=Path('test_resources/MutualReceipt/export').read_bytes();lines=source.splitlines();original=json.loads(lines[-1]);assert len(original['inductive']['types'])==2
cases=[('valid',source,0)]
def add(name,change,expected=1):
 obj=copy.deepcopy(original);change(obj['inductive']);data=b'\n'.join(lines[:-1]+[json.dumps(obj,separators=(',',':')).encode()])+b'\n';cases.append((name,data,expected))
add('nonowner-recursion-flag',lambda b:b['types'][1].update(isRec=True))
add('nonowner-index-count',lambda b:b['types'][1].update(numIndices=1))
add('nonowner-constructor-fields',lambda b:b['ctors'][1].update(numFields=2))
add('nonowner-constructor-index',lambda b:b['ctors'][1].update(cidx=1))
add('nonowner-duplicate-universe',lambda b:b['types'][1].update(levelParams=[23,23]))
add('nonowner-duplicate-declared-universe',lambda b:b['types'][1].update(levelParams=[3,3]))
add('nonowner-nested-flag',lambda b:b['types'][1].update(numNested=1))
add('nonowner-recursor-type',lambda b:b['recs'][0].update(type=0))
add('nonowner-rule-fields',lambda b:b['recs'][0]['rules'][0].update(nfields=2))
add('different-member-order-fallback',lambda b:b['types'][1].update(all=[24,23]),None)
rows=[]
for threads in [1,2]:
 cfg=a.out/f'config-{threads}.json';cfg.write_text(json.dumps({'use_stdin':True,'num_threads':threads,'nat_extension':True,'string_extension':True,'unsafe_permit_all_axioms':True,'unpermitted_axiom_hard_error':False,'print_success_message':True}))
 for name,data,expected in cases:
  observed={}
  for arm,binary in [('baseline',a.baseline),('candidate',a.candidate)]:
   cmd=[str(binary.resolve()),str(cfg.resolve())]
   if arm=='candidate' and a.candidate_upstream:cmd=[str(binary.resolve()),'--stdin','--threads',str(threads),'--nat-extension','--string-extension','--axiom-allow-all']
   r=subprocess.run(cmd,input=data,capture_output=True,timeout=60)
   observed[arm]=r.returncode
   rows.append({'case':name,'arm':arm,'threads':threads,'sha256':hashlib.sha256(data).hexdigest(),'expected':expected,'raw_exit':r.returncode,'stdout':r.stdout.decode(),'stderr_tail':r.stderr.decode()[-800:]})
  (a.out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
  if not a.candidate_upstream:assert observed['baseline']==observed['candidate'],(name,observed)
  if expected is not None and not a.candidate_upstream:assert observed['candidate']==expected,(name,observed,expected)
summary={'state':'WARRANTED_BOUNDED_MUTUAL_CONTROLS','cases':len(cases),'observations':len(rows),'threads':[1,2],'boundary':'Ten prescribed source-derived controls and one baseline differential fallback. Not all Arena cases or full Mathlib.'}

if a.candidate_upstream:
 summary['state']='SOURCE_BOUNDARY_CONTROL_OBSERVATIONS'
 summary['strict_status_differences']=[r for r in rows if r['arm']=='candidate' and r['expected'] is not None and r['raw_exit']!=r['expected']]
 summary['invalid_accepted']=[r for r in rows if r['arm']=='candidate' and r['expected']==1 and r['raw_exit']==0]
 summary['valid_not_accepted']=[r for r in rows if r['arm']=='candidate' and r['expected']==0 and r['raw_exit']!=0]
 summary['boundary']='Raw source-boundary observations. Exit 3 with the retained panic is an internal parser failure, not a semantic REJECT. The original duplicate-universe control refers to a name without a declared Param level; the additional declared-universe control uses existing Param name 3. Differential-only fallback has no expected semantic verdict.'
(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
