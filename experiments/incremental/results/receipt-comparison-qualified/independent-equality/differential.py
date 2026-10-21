#!/usr/bin/env python3
"""Independent canonical-reference differential; no producers/checkers/caches run."""
import argparse,ast,copy,hashlib,importlib,json,math,random,subprocess,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
def sha(x):return hashlib.sha256(x).hexdigest()
def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def fn_text(raw,name):
 text=raw.decode();node=next(n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))and n.name==name)
 return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno]).encode()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for flag in ['repo','ci-zip','original-index-root','expanded-index-root','out']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 source=a.repo/'experiments/incremental/producer_delta.py';before=source.read_bytes()
 sys.path.insert(0,str(source.parent));adapter=importlib.import_module('producer_delta')
 old=subprocess.check_output(['git','show','6e717043b85acdad63c2399131cb5f9a7432ee37:experiments/incremental/producer_delta.py'],cwd=a.repo)
 assert fn_text(before,'authenticate_sparse_acceptance')==fn_text(old,'authenticate_sparse_acceptance')
 check=adapter._same_index_json;results=[];index_reports=[]
 def case(label,left,right):
  expected=encoded(left)==encoded(right);actual=check(left,right);reverse=check(right,left)
  record=dict(label=label,expected=expected,actual=actual,reverse=reverse)
  results.append(record);assert actual is expected and reverse is expected,record
 def replace_row(x,pos=0,**fields):
  out=dict(x,declarations=list(x['declarations']));out['declarations'][pos]=dict(x['declarations'][pos],**fields);return out
 with zipfile.ZipFile(a.ci_zip)as z:
  reports={profile:json.loads(z.read(f'retained-admission-protected/{profile}/protected-matrix/retained_selected/summary.json'))for profile in ['original','expanded']}
 for profile,root in [('original',a.original_index_root),('expanded',a.expanded_index_root)]:
  for variant in ['baseline','early-definition','unrelated-definition','theorem-leaf']:
   path=root/variant/'native/index.json';raw=path.read_bytes();x=json.loads(raw);canonical=encoded(x)
   assert sha(canonical)==reports[profile]['references'][variant]['typed_index_sha256'],(profile,variant)
   assert x['count']==(3436 if profile=='original' else 11653)
   def c(label,left,right):case(profile+'/'+variant+'/'+label,left,right)
   start=len(results);c('same-root-identity',x,x)
   c('shared-top-level-copy',x,dict(x))
   c('shared-declaration-list-copy',x,dict(x,declarations=list(x['declarations'])))
   c('independent-deep-copy',x,copy.deepcopy(x))
   c('independent-JSON-roundtrip',x,json.loads(canonical))
   c('dictionary-insertion-order',x,dict(reversed(list(x.items()))))
   c('late-shared-row-copy',x,replace_row(x,len(x['declarations'])-1))
   for pos in [0,len(x['declarations'])//2,len(x['declarations'])-1]:
    for field in ['own','closure']:
     oldv=x['declarations'][pos][field];newv=('0'if oldv[0]!='0'else'1')+oldv[1:]
     c(f'mutated-{field}-{pos}',x,replace_row(x,pos,**{field:newv}))
   c('integer-vs-bool',x,replace_row(x,0,index=False))
   c('integer-vs-float',x,replace_row(x,0,index=0.0))
   c('signed-zero',replace_row(x,0,index=0.0),replace_row(x,0,index=-0.0))
   c('distinct-NaNs',replace_row(x,0,index=float('nan')),replace_row(x,0,index=-float('nan')))
   c('count-numeric-type',x,dict(x,count=float(x['count'])))
   c('mutated-dependencies',x,replace_row(x,0,deps=x['declarations'][0]['deps']+['0'*64]))
   c('mutated-name',x,replace_row(x,0,name=x['declarations'][0]['name']+'x'))
   c('mutated-schedule',x,dict(x,schedule='0'*64))
   c('non-ASCII-value-alias',replace_row(x,0,name='\U0001f600'),replace_row(x,0,name='\ud83d\ude00'))
   c('non-ASCII-key-alias',dict(x,meta={'\U0001f600':1}),dict(x,meta={'\ud83d\ude00':1}))
   c('non-ASCII-duplicate-rendered-key-order',dict(x,meta={'\U0001f600':1,'\ud83d\ude00':2}),dict(x,meta={'\ud83d\ude00':2,'\U0001f600':1}))
   c('unsupported-tuple-legacy-fallback',dict(x,meta={'probe':(1,2)}),dict(x,meta={'probe':[1,2]}))
   index_reports.append(dict(profile=profile,variant=variant,path=str(path),file_sha256=sha(raw),canonical_sha256=sha(canonical),canonical_bytes=len(canonical),count=x['count'],cases=len(results)-start,ci_reference_pin_matched=True))
 # Small independently generated cases include DAG sharing and copied structure.
 rng=random.Random(561921);atoms=[None,True,False,0,1,-1,0.0,-0.0,float('nan'),float('inf'),'ASCII','α','\U0001f600','\ud83d\ude00']
 def tree(depth):
  if depth==0 or rng.randrange(4)==0:return rng.choice(atoms)
  if rng.randrange(2):return [tree(depth-1)for _ in range(rng.randrange(4))]
  return {'k'+str(i):tree(depth-1)for i in range(rng.randrange(4))}
 for n in range(700):
  x=tree(5);case('generated-copy/'+str(n),x,copy.deepcopy(x));case('generated-unrelated/'+str(n),x,tree(5))
 for depth in [8,32,64,128]:
  x=0
  for _ in range(depth):x={'child':x}
  case('nested-depth/'+str(depth),x,copy.deepcopy(x))
 # Probe a broader JSON input outside actual schema to record recursion boundary.
 depth_probes=[]
 for depth in [200,350,500]:
  x=0;y=0
  for _ in range(depth):x={'child':x};y={'child':y}
  legacy=encoded(x)==encoded(y)
  try:actual=check(x,y);error=None
  except RecursionError as exc:actual=None;error=type(exc).__name__
  depth_probes.append(dict(depth=depth,legacy_equal=legacy,actual=actual,error=error,scope='outside observed real-index schema; domain-limit probe'))
 assert source.read_bytes()==before,'source drift during differential'
 report=dict(status='PASS_REAL_INDEX_AND_ADVERSARIAL_CANONICAL_REFERENCE_DIFFERENTIAL',cases=len(results),indexes=index_reports,results=results,depth_probes=depth_probes,source_path=str(source),source_sha256=sha(before),comparator_sha256=sha(fn_text(before,'_same_index_json')),authenticate_sparse_acceptance_unchanged=True,ci_zip_sha256=sha(a.ci_zip.read_bytes()),helper_sha256=sha(Path(__file__).read_bytes()),scope=['Comparator correctness differential only; no economic or fresh kernel qualification.','All eight real saved native indexes match candidate-CI typed-index pins.','Adversarial mutations include schema-invalid scalar forms to test canonical equality semantics; they are not admitted receipts.','Real-index comparisons passed in both directions; depth probes separately report broader generic-JSON limits.'])
 (a.out/'summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(status=report['status'],cases=len(results),indexes=len(index_reports),depth_probes=depth_probes,summary_sha256=sha((a.out/'summary.json').read_bytes()))))
if __name__=='__main__':main()
