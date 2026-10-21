#!/usr/bin/env python3
"""Direct native baseline+delta protocol and fresh oracles; no engine imports."""
import argparse,hashlib,importlib.util,json,os,fcntl,subprocess,time
from pathlib import Path
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fh(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for raw in iter(lambda:f.read(1<<20),b''):h.update(raw)
 return h.hexdigest()
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def write(path,x):Path(path).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def config(path):return dict(export_file_path=str(path),permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True,nat_extension=True,string_extension=True,num_threads=1,use_stdin=False)
def select(old,new):
 compatible=enc(old['meta'])==enc(new['meta']);globals_same=compatible and enc(old['builtins'])==enc(new['builtins'])and old['complex']==new['complex'];schedule_same=globals_same and old['schedule']==new['schedule'];past={d['key']:d for d in old['declarations']}if compatible else{};prefix=True;out=[]
 for d in new['declarations']:
  prior=past.get(d['key']);prefix=prefix and globals_same and prior is not None and prior['index']==d['index']and prior['own']==d['own'];local=schedule_same and d['kind']in['axiom','def','thm','opaque']and prior is not None and prior['own']==d['own']and prior['closure']==d['closure']
  if not(prefix or local):out.append(d['index'])
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['inputs','recipe-dir','original-qualification','expanded-qualification','tools','full-summary','out']:p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);paths=json.loads(a.tools.read_bytes());full=json.loads(a.full_summary.read_bytes());recipes=json.loads((a.recipe_dir/'recipes.json').read_bytes());tools={k:dict(path=str(Path(v).resolve()),sha256=fh(v))for k,v in paths.items()}
 for k,v in tools.items():assert v['sha256']==full['tools'][k]['sha256']
 spec=importlib.util.spec_from_file_location('standalone_decoder',Path(__file__).parent/'decoder.py');decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
 commands=[];cases=[];full_cases={(c['profile'],c['name']):c for c in full['cases']}
 def run(label,args,expected=None,request=None):
  begin=time.perf_counter();timed_out=False
  try:r=subprocess.run([str(v)for v in args],input=request,capture_output=True,timeout=180);code=r.returncode;stdout=r.stdout;stderr=r.stderr
  except subprocess.TimeoutExpired as e:code=None;stdout=e.stdout or b'';stderr=e.stderr or b'';timed_out=True
  (a.out/(label+'.stdout')).write_bytes(stdout);(a.out/(label+'.stderr')).write_bytes(stderr)
  record=dict(label=label,command=[str(v)for v in args],returncode=code,timed_out=timed_out,elapsed_seconds=time.perf_counter()-begin,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),expected_returncode=expected)
  if request is not None:(a.out/(label+'.stdin')).write_bytes(request);record['stdin_sha256']=sha(request)
  write(a.out/(label+'.command.json'),record);commands.append(record)
  assert not timed_out and code not in[126,127]and(expected is None or code==expected),record
  return record,stdout,stderr
 def render(n):return''if n[0]=='anonymous'else(render(n[1])+'.'if render(n[1])else'')+str(n[2])
 for profile,qualification in [('original',a.original_qualification),('expanded',a.expanded_qualification)]:
  baseline=(a.inputs/(profile+'-baseline.ndjson')).resolve();assert fh(baseline)==recipes['baselines'][profile]['sha256'];layout=decoder.baseline(baseline);names=layout[0]
  old=json.loads((qualification/'references/baseline/native/index.json').read_bytes());basecfg=a.out/(profile+'-baseline.config.json');write(basecfg,config(baseline))
  q=json.loads((qualification/'summary.json').read_bytes())
  for name in ['early-definition','unrelated-definition','signed-invalid-proof','unused-invalid-node-zero-selection-parser','overwrite-admitted-expression']:
   label=profile+'-'+name;fd=None
   if name in ['early-definition','unrelated-definition']:
    delta_files=list((qualification/'samples'/(name+'-0')/'session/cache/deltas').glob('*.ndjson'));assert len(delta_files)==1;delta=delta_files[0].read_bytes();new=json.loads((qualification/'references'/name/'native/index.json').read_bytes());indices=select(old,new)
    assert len(indices)==({'original':{'early-definition':413,'unrelated-definition':1},'expanded':{'early-definition':672,'unrelated-definition':260}}[profile][name]);expected=0
   elif name=='overwrite-admitted-expression':delta=b'{"ie":2,"sort":0}\n';indices=[];expected=1
   else:
    recipe=next(c for c in recipes['cases']if c['profile']==profile and c['name']==name);delta=(a.recipe_dir/recipe['delta']).read_bytes();assert sha(delta)==recipe['delta_sha256'];indices=list(range(old['count']))if name=='signed-invalid-proof'else[];expected=1
   expected_names=[]
   for raw in delta.splitlines():
    row=json.loads(raw)
    for tag in ['def','thm','opaque','axiom']:
     if tag in row:expected_names.append(render(names[row[tag]['name']]))
   dpath=a.out/(label+'.delta.ndjson');dpath.write_bytes(delta);ipath=a.out/(label+'.indices.json');write(ipath,indices)
   request=dict(delta_path=str(dpath.resolve()),delta_sha256=sha(delta),selected_indices_path=str(ipath.resolve()),expected_changed_names=expected_names)
   record,stdout,stderr=run(label+'-retained',[tools['retained-native']['path'],basecfg,recipes['baselines'][profile]['sha256']],expected,enc(request)+b'\n')
   responses=[json.loads(line)for line in stdout.splitlines()];assert len(responses)==2 and responses[0]['status']=='ready'and responses[0]['baseline_sha256']==recipes['baselines'][profile]['sha256']
   result=responses[1];assert result['status']==('checked'if expected==0 else'rejected')and result['code']==expected
   if expected==0:assert result['checked']==len(indices)and result['total_declarations']==old['count']
   if name=='signed-invalid-proof':assert'selected declaration checker thread panicked'in result['reason']
   if name.startswith('unused-'):assert'not-an-integer'in result['reason']
   if name.startswith('overwrite-'):assert'overwrites admitted baseline'in result['reason']
   record['classification']='SELECTED_ACCEPTED'if expected==0 else('KERNEL_REJECTED'if name=='signed-invalid-proof'else'PARSER_POLICY_REFUSED'if name.startswith('overwrite-')else'PARSER_REFUSED_ZERO_SELECTED')
   if name in ['unrelated-definition','overwrite-admitted-expression']:
    fd=os.memfd_create('independent-retained-oracle',os.MFD_ALLOW_SEALING);composite=Path(f'/proc/{os.getpid()}/fd/{fd}');digest,size=decoder.reconstruct(layout,delta,composite);fcntl.fcntl(fd,1033,15);assert fcntl.fcntl(fd,1034)&15==15
    if name=='unrelated-definition':
     sample=next(s for s in q['samples']if s['variant']==name and not s['cold_replay']);assert digest==sample['snapshot']['sha256']and size==sample['snapshot']['bytes']
   else:
    composite=(a.inputs/(label+'.ndjson')).resolve();digest=fh(composite);size=composite.stat().st_size;assert digest==full_cases[profile,name]['sha256']
   cfg=a.out/(label+'.fresh.config.json');write(cfg,config(composite))
   fresh,fout,ferr=run(label+'-fresh-selected',[tools['current-zero-selected']['path'],cfg,ipath],None if name.startswith('overwrite-')else expected)
   fresh['classification']='FRESH_SELECTED_ACCEPTED'if fresh['returncode']==0 else'FRESH_KERNEL_REJECTED'if name=='signed-invalid-proof'else'FRESH_PARSER_REFUSED'
   if name=='unrelated-definition':
    oracles=[]
    for tool in ['current-rust','normal-cpp','paranoid-cpp']:
     args=[tools[tool]['path'],cfg]if tool.endswith('rust')else[tools[tool]['path'],'--silent','--from-export',composite]
     oracle,_,_=run(label+'-'+tool,args,0);oracle['classification']='FULL_ACCEPTED';oracles.append(oracle)
   else:oracles=full_cases.get((profile,name),{}).get('runs',[])
   cases.append(dict(profile=profile,name=name,delta_sha256=sha(delta),delta_bytes=len(delta),complete_input_sha256=digest,complete_input_bytes=size,expected_changed_names=expected_names,selected_indices=indices,selected_count=len(indices),native=record,responses=responses,fresh_selected=fresh,full_oracles=oracles,scope='Native is low-level parser/checking witness, not HMAC acceptance; overwrite guard may conservatively refuse bytes accepted by fresh parser.'))
   if fd is not None:os.close(fd)
   write(a.out/'progress.json',dict(cases_completed=len(cases),commands_completed=len(commands)))
  del layout
 for k,v in tools.items():assert fh(v['path'])==v['sha256']
 assert len(cases)==10 and len(commands)==26
 report=dict(status='PASS_DIRECT_RETAINED_PROTOCOL_AND_FRESH_ORACLES',source=full['source'],tools=tools,cases=cases,native_sessions=10,fresh_selected_commands=10,additional_full_commands=6,helper_sha256=fh(__file__),decoder_sha256=fh(Path(__file__).parent/'decoder.py'),full_replay_summary_sha256=fh(a.full_summary),scope=['No producer_delta, engine, receipt decoder, or current incremental verifier imports.','Positive indices derived independently from saved full native indexes; invalid proof deliberately checks ALL declarations.','Existing complete files reused; unrelated/overwrite complete bytes independently reconstructed in sealed memfds without durable large files.','All raw protocol input/output preserved; no issuer key or acceptance receipt exists in this replay.','Native private parser state is coldly reconstructed for each single request; this is correctness evidence, not economics.'])
 write(a.out/'summary.json',report);print(json.dumps(dict(status=report['status'],native_sessions=10,commands=26,summary_sha256=fh(a.out/'summary.json'))))
if __name__=='__main__':main()
