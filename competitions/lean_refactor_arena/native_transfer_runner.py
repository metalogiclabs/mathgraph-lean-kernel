#!/usr/bin/env python3
"""Bounded primary acquisition and conditional full-version qualification.

Reuses the existing candidate grammar, native closure proposal, and admission
frontier. No mathematical proof operation is invented by this orchestration.
"""
import argparse,json,subprocess,sys
from pathlib import Path
from frontier_reclose import decide
from native_closure_discovery import digest,repair
from native_diagnostic import capture
from public_harness_bridge import slug

PIN='7f3a401470d04f70013d293db4253b088ec8a0ae'

def assert_pinned_clean(comp,expected=PIN):
 try:
  actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=comp,text=True,stderr=subprocess.DEVNULL).strip()
  clean=subprocess.run(['git','diff','--quiet','HEAD','--','.'],cwd=comp).returncode==0
 except subprocess.CalledProcessError as exc:raise ValueError('missing public harness revision') from exc
 if actual!=expected:raise ValueError('wrong public harness revision')
 if not clean:raise ValueError('modified tracked public harness inputs')

def acquire_repair(row,result,diagnostic,source_start):
 if result.get('compiled') is not False:return None
 errors=[e for p in result.get('per_version',[]) for e in p.get('errors',[])]
 if errors!=['unsolved goals']:return None
 if result.get('proof_sha256')!=digest(row['proof']):raise ValueError('native parent source mismatch')
 if diagnostic.get('status')!='completed' or diagnostic.get('returncode')!=1:return None
 return repair(row,diagnostic['output'],source_start)

def write_rows(path,rows):
 path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--competition',required=True);ap.add_argument('--bank',required=True);ap.add_argument('--out',required=True)
 a=ap.parse_args();comp=Path(a.competition).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 if any(out.iterdir()):raise ValueError('output directory must be empty')
 assert_pinned_clean(comp)
 rows=[json.loads(x) for x in Path(a.bank).read_text().splitlines()]
 benchmark={r['name']:r for r in map(json.loads,(comp/'benchmark_data_warmup.jsonl').read_text().splitlines())}
 bank=out/'bank.jsonl';write_rows(bank,rows)
 script=Path(__file__).resolve().parent/'public_harness_bridge.py'
 primary=[];diagnostics={}
 def measure(row,phase,all_versions=False):
  subprocess.run([sys.executable,str(script),'--competition',str(comp),'--project','v4.31','--name',row['name'],'--candidate',str(bank),'--label',row['label']],check=True)
  cmd=[sys.executable,'arena.py','check','--name',row['name'],'--timeout','1800']
  if all_versions:cmd+=['--all-versions']
  p=subprocess.run(cmd,cwd=comp,text=True,capture_output=True,timeout=7500)
  key=phase+'_'+slug(row['name'])+'_'+row['label']
  (out/(key+'.log')).write_text(p.stdout+'\n'+p.stderr)
  result=json.loads(p.stdout)
  result.update(name=row['name'],candidate_label=row['label'],operator=row['operator'],proof_sha256=digest(row['proof']),public_harness_sha=PIN,measurement_scope='all_required' if all_versions else 'primary_only')
  with (out/(phase+'.jsonl')).open('a') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
  print(json.dumps(result,ensure_ascii=False),flush=True)
  if not result.get('compiled') and not all_versions:
   diagnostic=capture(['lake','env','lean','Arena/'+slug(row['name'])+'.lean'],comp/'projects/v4.31')
   diagnostics[(row['name'],row['label'])]=diagnostic
   (out/(key+'.diagnostic.json')).write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2)+'\n')
  return result
 for row in list(rows):
  result=measure(row,'primary');primary.append(result)
  if row['operator']=='control':continue
  diagnostic=diagnostics.get((row['name'],row['label']),{})
  child=acquire_repair(row,result,diagnostic,benchmark[row['name']]['start_line'])
  if child:
   rows.append(child);write_rows(bank,rows);primary.append(measure(child,'primary'))
 decisions={};promoted=[]
 for name in dict.fromkeys(r['name'] for r in rows):
  candidates=[r for r in rows if r['name']==name];control=next(r for r in candidates if r['operator']=='control')
  d=decide(candidates,[r for r in primary if r['name']==name],expected_name=name,required_versions=['v4.31.0'],expected_public_sha=PIN,incumbent_label=control['label'])
  decisions[name]=d
  if d['objective_gain']>0:promoted.extend([control,next(r for r in candidates if r['label']==d['selected_label'])])
 (out/'primary-selection.json').write_text(json.dumps(dict(scope='primary_only',decisions=decisions),indent=2)+'\n')
 if not promoted:return
 # Frozen Binius pair only. Explicit version lists remain final admission authority.
 required={r['name']:['v4.31.0','v4.30.0','v4.29.0']+(['v4.28.0'] if 'fiberwise' in r['name'] else []) for r in promoted}
 if set(required)-{'Binius.BinaryBasefold.fiberwise_dist_lt_imp_dist_lt_unique_decoding_radius','Binius.BinaryBasefold.fold_advances_evaluation_poly'}:raise ValueError('unsupported full-version project')
 versions=set(v for vs in required.values() for v in vs)-{'v4.31.0'}
 for version in sorted(versions):
  project=comp/'projects'/version.removesuffix('.0')
  for args in [['lake','update'],['lake','exe','cache','get'],['lake','build','ArkLib.ProofSystem.Binius.BinaryBasefold.Prelude']]:
   with (out/(version+'-build.log')).open('a') as log:
    p=subprocess.run(args,cwd=project,stdout=log,stderr=subprocess.STDOUT)
   if p.returncode and args!=['lake','exe','cache','get']:raise RuntimeError('targeted version build failed: '+version)
 qualified=[measure(r,'qualification',True) for r in promoted]
 final={}
 for name,versions in required.items():
  cs=[r for r in promoted if r['name']==name]
  final[name]=decide(cs,[r for r in qualified if r['name']==name],expected_name=name,required_versions=versions,expected_public_sha=PIN,incumbent_label=next(r['label'] for r in cs if r['operator']=='control'))
 (out/'qualification-selection.json').write_text(json.dumps(final,indent=2)+'\n')
if __name__=='__main__':main()
