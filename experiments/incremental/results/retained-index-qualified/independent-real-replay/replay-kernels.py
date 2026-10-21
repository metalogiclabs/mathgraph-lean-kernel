#!/usr/bin/env python3
"""Portable replay of the ten inputs: 40 full kernels + eight zero parsers.

Supply outputs of reconstruct-inputs.py and tool paths. Exact observed executable
hashes are required by default. --allow-new-builds creates a separately labeled
fresh-build replay and never changes the preserved historical observations.
"""
import argparse,hashlib,importlib.util,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def file_hash(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for raw in iter(lambda:f.read(1<<20),b''):h.update(raw)
 return h.hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def config(path):return dict(export_file_path=str(path),permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True,nat_extension=True,string_extension=True,num_threads=1,use_stdin=False)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True)
 p.add_argument('--tools',type=Path,required=True,help='JSON object mapping all eight recipe tool names to executable paths')
 p.add_argument('--original-source-export',type=Path,required=True);p.add_argument('--expanded-source-export',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-new-builds',action='store_true');a=p.parse_args()
 if not __debug__:raise ValueError('run without Python -O')
 r=load(HERE/'recipes.json');paths=load(a.tools);out=a.out.resolve()
 if out.exists()and any(out.iterdir()):raise ValueError('use a fresh output directory')
 out.mkdir(parents=True,exist_ok=True)
 assert set(paths)==set(r['tools'])
 tools={}
 for name,path in paths.items():
  path=Path(path).resolve();actual=file_hash(path);expected=r['tools'][name]['sha256']
  if not a.allow_new_builds:assert actual==expected,(name,'executable differs from observed pin')
  tools[name]=dict(path=str(path),sha256=actual,recorded_sha256=expected,matches_recorded=actual==expected)
 def command(name,args,expected):
  start=time.perf_counter();run=subprocess.run([str(x)for x in args],capture_output=True,timeout=180)
  (out/(name+'.stdout')).write_bytes(run.stdout);(out/(name+'.stderr')).write_bytes(run.stderr)
  result=dict(command=[str(x)for x in args],returncode=run.returncode,expected_returncode=expected,
   elapsed_seconds=time.perf_counter()-start,stdout_sha256=sha(run.stdout),stderr_sha256=sha(run.stderr))
  write(out/(name+'.command.json'),result);assert run.returncode==expected,result
  return result,run.stdout
 cases=[]
 for case in r['cases']:
  name=case['profile']+'-'+case['name'];path=(a.inputs/(name+'.ndjson')).resolve()
  assert file_hash(path)==case['expected_sha256']and path.stat().st_size==case['expected_bytes']
  cfg=out/(name+'.config.json');write(cfg,config(path));runs=[]
  for tool in ['current-rust','qualified449-rust','normal-cpp','paranoid-cpp']:
   args=[tools[tool]['path'],cfg]if tool.endswith('rust')else[tools[tool]['path'],'--silent','--from-export',path]
   runs.append(command(name+'-'+tool,args,case['expected_returncode'])[0])
  if case['zero_selected_parser']:
   indices=out/(name+'.indices.json');indices.write_text('[]\n')
   for tool in ['current-zero-selected','qualified449-zero-selected']:
    runs.append(command(name+'-'+tool,[tools[tool]['path'],cfg,indices],1)[0])
  cases.append(dict(profile=case['profile'],name=case['name'],sha256=case['expected_sha256'],commands=runs))
 oracle_path=HERE/'as-run/qualified449_full_python_index.py'
 assert file_hash(oracle_path)==r['qualified_baseline_python_sha256']
 spec=importlib.util.spec_from_file_location('qualified449_full_index_only',oracle_path)
 oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 indexes={}
 for profile,source in [('original',a.original_source_export),('expanded',a.expanded_source_export)]:
  source=source.resolve();assert file_hash(source)==r['source_exports'][profile]['sha256']
  composite=(a.inputs/(profile+'-early-definition.ndjson')).resolve();values=[];commands=[]
  for label,path,tool in [('current-composite',composite,'current-index'),('qualified449-composite',composite,'qualified449-index'),('pinned-source-export',source,'current-index')]:
   cfg=out/(profile+'-'+label+'.config.json');write(cfg,config(path))
   record,raw=command(profile+'-'+label+'-index',[tools[tool]['path'],cfg],0);values.append(json.loads(raw));commands.append(record)
  assert all(canonical(value)==canonical(values[0])for value in values)
  assert canonical(oracle.make_index(composite))==canonical(values[0])
  digest=sha(canonical(values[0]));assert digest==r['source_exports'][profile]['typed_index_sha256']
  indexes[profile]=dict(count=values[0]['count'],typed_index_sha256=digest,commands=commands)
 for info in tools.values():assert file_hash(info['path'])==info['sha256']
 assert len(cases)==10 and sum(len(c['commands'])for c in cases)==48
 summary=dict(status='PASS_PORTABLE_REAL_INPUT_KERNEL_AND_INDEX_REPLAY',full_kernel_commands=40,zero_selected_parser_commands=8,
  tools=tools,exact_recorded_binary_parity=all(t['matches_recorded']for t in tools.values()),cases=cases,indexes=indexes,
  helper_sha256=file_hash(__file__),recipes_sha256=file_hash(HERE/'recipes.json'),
  scope='Fresh correctness replay. Diagnostic times are not economic evidence; preserved as-run observations remain unchanged.')
 write(out/'summary.json',summary);print(json.dumps(dict(status=summary['status'],commands=48,exact_recorded_binary_parity=summary['exact_recorded_binary_parity'])))
if __name__=='__main__':main()
