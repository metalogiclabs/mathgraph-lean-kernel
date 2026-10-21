#!/usr/bin/env python3
"""Standalone exact-input four-oracle replay; no incremental module imports."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
SOURCE='5dfe38b01ca7b1c67f70be4ffb2479978049239e'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fh(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for raw in iter(lambda:f.read(1<<20),b''):h.update(raw)
 return h.hexdigest()
def write(path,x):Path(path).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def config(path):return dict(export_file_path=str(path),permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True,nat_extension=True,string_extension=True,num_threads=1,use_stdin=False)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['repo','inputs','recipes','candidate-pins','tools','out']:p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 recipes=json.loads(a.recipes.read_bytes());pins=json.loads(a.candidate_pins.read_bytes());paths=json.loads(a.tools.read_bytes())
 tools={k:dict(path=str(Path(v).resolve()),sha256=fh(v))for k,v in paths.items()}
 for name,pinname in [('current-rust','sokonanoda'),('current-zero-selected','check-selected'),('retained-native','check-selected-retained-session')]:assert tools[name]['sha256']==pins[pinname]
 for name in ['qualified449-rust','qualified449-zero-selected','normal-cpp','paranoid-cpp']:assert tools[name]['sha256']==recipes['tools'][name]['sha256']
 source_parity={}
 files=subprocess.check_output(['git','ls-tree','-r','--name-only',SOURCE,'src'],cwd=a.repo,text=True).splitlines()+['Cargo.toml','Cargo.lock']
 for name in files:
  old=subprocess.check_output(['git','show','6e717043b85acdad63c2399131cb5f9a7432ee37:'+name],cwd=a.repo)
  new=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=a.repo);assert old==new,name;source_parity[name]=sha(new)
 commands=[];cases=[]
 def run(label,args,expected,category):
  tick=time.perf_counter();timeout=False
  try:r=subprocess.run([str(v)for v in args],capture_output=True,timeout=180);code=r.returncode;stdout=r.stdout;stderr=r.stderr
  except subprocess.TimeoutExpired as e:code=None;stdout=e.stdout or b'';stderr=e.stderr or b'';timeout=True
  (a.out/(label+'.stdout')).write_bytes(stdout);(a.out/(label+'.stderr')).write_bytes(stderr)
  result=dict(command=[str(v)for v in args],returncode=code,timed_out=timeout,expected_returncode=expected,classification='TIMEOUT_UNKNOWN'if timeout else('UNSUPPORTED_EXECUTION_UNKNOWN'if code in [126,127]else category if code==expected else'UNEXPECTED_UNKNOWN'),elapsed_seconds=time.perf_counter()-tick,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
  write(a.out/(label+'.command.json'),result);commands.append(result);assert not timeout and code==expected,result
  return result
 for case in recipes['cases']:
  name=case['profile']+'-'+case['name'];path=(a.inputs/(name+'.ndjson')).resolve();assert fh(path)==case['expected_sha256']and path.stat().st_size==case['expected_bytes']
  cfg=a.out/(name+'.config.json');write(cfg,config(path));runs=[];category='ACCEPTED'if case['expected_returncode']==0 else('PARSER_REFUSED'if case['zero_selected_parser']else'KERNEL_REJECTED')
  for tool in ['current-rust','qualified449-rust','normal-cpp','paranoid-cpp']:
   args=[tools[tool]['path'],cfg]if tool.endswith('rust')else[tools[tool]['path'],'--silent','--from-export',path]
   runs.append(run(name+'-'+tool,args,case['expected_returncode'],category))
  if case['zero_selected_parser']:
   indices=a.out/(name+'.indices.json');indices.write_text('[]\n')
   for tool in ['current-zero-selected','qualified449-zero-selected']:runs.append(run(name+'-'+tool,[tools[tool]['path'],cfg,indices],1,'PARSER_REFUSED_ZERO_SELECTED'))
  cases.append(dict(profile=case['profile'],name=case['name'],sha256=case['expected_sha256'],bytes=case['expected_bytes'],runs=runs))
  write(a.out/'progress.json',dict(cases_completed=len(cases),commands_completed=len(commands)))
 for name,tool in tools.items():assert fh(tool['path'])==tool['sha256'],name
 assert len(cases)==10 and len(commands)==48
 report=dict(status='PASS_FRESH_STANDALONE_40_FULL_8_ZERO_SELECTED',source=SOURCE,source_Rust_unchanged_from6e=source_parity,tools=tools,cases=cases,full_kernel_commands=40,zero_selected_parser_commands=8,helper_sha256=fh(__file__),recipes_sha256=fh(a.recipes),scope=['Actual standalone kernel processes on independently hash-pinned complete input bytes; no producer_delta or engine imports.','Times diagnostic only, not benchmark; executable hashes separately identify current and preserved449 builds.','Negative semantic classifications follow the fixed malformed-node/proof/axiom fixtures and preserved raw diagnostics; code127 is never rejection.'])
 write(a.out/'summary.json',report);print(json.dumps(dict(status=report['status'],commands=48,summary_sha256=fh(a.out/'summary.json'))))
if __name__=='__main__':main()
