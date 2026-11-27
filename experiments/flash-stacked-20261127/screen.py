"""Measure stacks and their parent independently with frozen executable IDs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

p=argparse.ArgumentParser();p.add_argument('--arms',default='baseline,projection,pi,pic,pib18,pib36,picb36');p.add_argument('--name',default='matrix');p.add_argument('--baseline',default='baseline');p.add_argument('--parent',default='projection');p.add_argument('--threads',type=int,default=2);p.add_argument('--native-rounds',type=int,default=4);a=p.parse_args()
WORK=Path(os.environ.get('FLASH_STACK_WORK','/tmp/flash-stack-work'))
OUT=WORK/'evidence'/a.name;OUT.mkdir(exist_ok=False)
BIN=WORK/'evidence/builds';fixture=Path('/tmp/flash-runtime/mathlib-prefix.ndjson')
drrun=Path('/workspace/scratch/f55dc021446a/diagnostics/dynamorio/bin64/drrun');client=Path('/workspace/scratch/f55dc021446a/diagnostics/counter-v1.so')
arms=a.arms.split(',');assert a.baseline in arms and a.parent in arms
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x):(OUT/name).write_text(json.dumps(x,indent=2)+'\n')
assert fixture.stat().st_size==134232002 and sha(fixture)=='c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
assert sha(client)=='212a57d6dedc34155467d196e76d30b5d50ceb15010212c4c0f65dd6914194ce'
hashes={arm:sha(BIN/(arm+'.bin')) for arm in arms};assert len(set(hashes.values()))==len(hashes)
save('identity.json',{'executables':hashes,'input_sha256':sha(fixture),'client_sha256':sha(client),'drrun_sha256':sha(drrun),'checking_workers':a.threads,'boundary':'Fixed prefix; generic-build software instruction counts and matched-build native resources. No full-input or Arena rank claim.'})
calibration=[]
for n in [1,17,1000000]:
 src=OUT/f'loop-{n}.S';binary=OUT/f'loop-{n}.bin'
 src.write_text('.global _start\n.text\n_start:\n'+f' movl ${n}, %ecx\n xorl %eax, %eax\n'+'again:\n addl $1, %eax\n decl %ecx\n jnz again\n movl $60, %eax\n xorl %edi, %edi\n syscall\n')
 subprocess.run(['gcc','-nostdlib','-no-pie',str(src),'-o',str(binary)],check=True)
 r=subprocess.run([str(drrun),'-c',str(client),'--',str(binary)],capture_output=True,timeout=30)
 (OUT/f'loop-{n}.stderr').write_bytes(r.stderr);hits=re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',r.stderr)
 count=int(hits[0]) if len(hits)==1 else None
 assert r.returncode==0 and count==3*n+5
 calibration.append({'n':n,'observed':count,'expected':3*n+5,'raw_exit':r.returncode})
save('calibration.json',calibration)

def execute(arm,tag,instrumented):
 assert {x:sha(BIN/(x+'.bin')) for x in arms}==hashes
 command=([str(drrun),'-c',str(client),'--'] if instrumented else [])+[str(BIN/(arm+'.bin')),'--stdin','--threads',str(a.threads),'--nat-extension','--string-extension','--axiom-allow-all']
 start=time.monotonic()
 with fixture.open('rb') as inp,(OUT/(tag+'.stdout')).open('wb') as out,(OUT/(tag+'.stderr')).open('wb') as err:
  process=subprocess.Popen(command,stdin=inp,stdout=out,stderr=err,start_new_session=True)
  # os.wait4 retains resource use for this exact process rather than cumulative
  # child counters. The wrapper's deadline is longer than this bounded screen.
  expired=[]
  def stop():
   expired.append(True)
   try:os.killpg(process.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  timer=threading.Timer(180,stop);timer.start()
  try:_,status,usage=os.wait4(process.pid,0);process.returncode=os.waitstatus_to_exitcode(status)
  finally:timer.cancel()
 stdout=(OUT/(tag+'.stdout')).read_bytes();stderr=(OUT/(tag+'.stderr')).read_bytes()
 row={'arm':arm,'raw_exit':process.returncode,'wall_s':time.monotonic()-start,'cpu_s':usage.ru_utime+usage.ru_stime,'peak_rss_kib':usage.ru_maxrss,'complete':bool(re.search(rb'checked 25131 declarations',stdout)),'timed_out':bool(expired)}
 if instrumented:
  hits=re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',stderr);row['instructions']=int(hits[0]) if len(hits)==1 else None
 print(tag,json.dumps(row),flush=True)
 assert row['raw_exit']==0 and row['complete'],row
 if instrumented:assert row['instructions'] is not None
 assert {x:sha(BIN/(x+'.bin')) for x in arms}==hashes
 return row

controls={};spans={}
for arm in dict.fromkeys([a.baseline,a.parent]):
 controls[arm]=[execute(arm,f'control-{arm}-{i}',True) for i in range(2)]
 vals=[r['instructions'] for r in controls[arm]];spans[arm]=(max(vals)-min(vals))/min(vals)
threshold=max(.01,2*max(spans.values()));save('prospective-threshold.json',{'controls':controls,'spans':spans,'minimum_reduction':threshold,'formula':'max(1%, twice the larger baseline/parent identical-executable control range), before candidate observations'})
rows=[]
for instrumented,rounds in [(True,2),(False,a.native_rounds)]:
 kind='instructions' if instrumented else 'native'
 for i in range(rounds):
  for arm in arms if i%2==0 else reversed(arms):
   row=execute(arm,f'{kind}-{arm}-{i}',instrumented);row.update(round=i,measurement=kind);rows.append(row);save('rows.json',rows)
results={}
for arm in arms:
 x={}
 for parent in dict.fromkeys([a.baseline,a.parent]):
  base=[r for r in rows if r['arm']==parent and r['measurement']=='instructions'];child=[r for r in rows if r['arm']==arm and r['measurement']=='instructions']
  paired=[child[i]['instructions']/base[i]['instructions'] for i in range(2)]
  ratio=sum(r['instructions'] for r in child)/sum(r['instructions'] for r in base)
  bn=[r for r in rows if r['arm']==parent and r['measurement']=='native'];cn=[r for r in rows if r['arm']==arm and r['measurement']=='native']
  x[parent]={'paired_ratios':paired,'aggregate_ratio':ratio,'gate_passed':all(v<=1-threshold for v in paired) and ratio<=1-threshold,'cpu_ratio':sum(r['cpu_s'] for r in cn)/sum(r['cpu_s'] for r in bn),'wall_ratio':sum(r['wall_s'] for r in cn)/sum(r['wall_s'] for r in bn),'peak_rss_ratio':max(r['peak_rss_kib'] for r in cn)/max(r['peak_rss_kib'] for r in bn)}
 results[arm]=x
save('summary.json',{'results':results,'threshold':threshold,'boundary':'Fixed-prefix two-worker combinations; observed counts, not sums of separate improvements. Complete Mathlib, native-target instructions and official rank remain UNKNOWN.'})
print('SUMMARY',json.dumps(results),flush=True)
