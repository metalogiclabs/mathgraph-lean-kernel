#!/usr/bin/env python3
"""Rebuild exact tested composites from pinned full baselines and included deltas.

No producer, incremental verifier or retained index is executed. --hash-only
validates all bytes without writing complete NDJSON files to the output folder.
"""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
SIMPLE={'axiom','def','thm','opaque'}
DECL=SIMPLE|{'quot','inductive'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def strict(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate key: '+key)
  result[key]=value
 return result
def load(path):return json.loads(Path(path).read_bytes(),object_pairs_hook=strict)
def file_hash(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for raw in iter(lambda:f.read(1<<20),b''):h.update(raw)
 return h.hexdigest()
def name_insert(names,row):
 if 'in'not in row:return
 ident=row['in'];assert type(ident)is int and ident not in names
 tag='str'if 'str'in row else'num';part=row[tag]
 names[ident]=(tag,names[part['pre']],part['str']if tag=='str'else part['i'])
def classify(raw):
 row=json.loads(raw,object_pairs_hook=strict);tags=set(row)&DECL
 assert len(tags)<=1
 return row,next(iter(tags))if tags else None
def baseline(path):
 names={0:('anonymous',)};dags=[];declarations=[]
 with Path(path).open('rb')as f:
  for raw in f:
   row,tag=classify(raw);name_insert(names,row)
   if tag is None:dags.append(raw)
   else:declarations.append(((tag,names[row[tag]['name']])if tag!='inductive'else None,raw))
 return names,dags,declarations
def reconstruct(layout,delta,output=None):
 names,dags,declarations=layout;names=dict(names);extra=[];replace={}
 for raw in delta.splitlines(keepends=True):
  assert raw.endswith(b'\n');row,tag=classify(raw);name_insert(names,row)
  if tag:
   assert tag in SIMPLE;key=(tag,names[row[tag]['name']]);assert key not in replace;replace[key]=raw
  else:assert'meta'not in row;extra.append(raw)
 h=hashlib.sha256();size=0;f=Path(output).open('wb')if output is not None else None
 def emit(raw):
  nonlocal size
  h.update(raw);size+=len(raw)
  if f is not None:f.write(raw)
 try:
  for raw in dags:emit(raw)
  for raw in extra:emit(raw)
  for key,raw in declarations:emit(replace.pop(key,raw))
  assert not replace
 finally:
  if f is not None:f.close()
 return h.hexdigest(),size
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--original-baseline',type=Path,required=True)
 p.add_argument('--expanded-baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--hash-only',action='store_true');a=p.parse_args()
 if not __debug__:raise ValueError('run without Python -O')
 r=load(HERE/'recipes.json');out=a.out.resolve()
 if out.exists()and any(out.iterdir()):raise ValueError('use a fresh output directory')
 out.mkdir(parents=True,exist_ok=True);results=[]
 for profile,path in [('original',a.original_baseline),('expanded',a.expanded_baseline)]:
  assert file_hash(path)==r['baselines'][profile]['sha256'] and path.stat().st_size==r['baselines'][profile]['bytes']
  layout=baseline(path)
  for case in r['cases']:
   if case['profile']!=profile:continue
   delta=(HERE/case['delta']).read_bytes();assert sha(delta)==case['delta_sha256']
   name=profile+'-'+case['name'];dest=None if a.hash_only else out/(name+'.ndjson')
   digest,size=reconstruct(layout,delta,dest)
   assert digest==case['expected_sha256']and size==case['expected_bytes'],name
   results.append(dict(profile=profile,name=case['name'],sha256=digest,bytes=size,path=str(dest)if dest else None))
 assert len(results)==10
 report=dict(status='PASS_EXACT_TEN_INPUT_RECONSTRUCTION',hash_only=a.hash_only,cases=results,
             helper_sha256=file_hash(__file__),recipes_sha256=file_hash(HERE/'recipes.json'),scope='Exact bytes only; no acceptance, issuer authentication or economic result')
 (out/'reconstruction.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(status=report['status'],cases=10,hash_only=a.hash_only)))
if __name__=='__main__':main()
