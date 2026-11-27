"""Measure source/compiler stack and worker argv as distinct interventions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

p=argparse.ArgumentParser();p.add_argument('--selected',required=True);a=p.parse_args()
work=Path('/tmp/flash-stack-work');out=work/'evidence/workers';out.mkdir(exist_ok=False)
bins=work/'evidence/builds';fixture=Path('/tmp/flash-runtime/mathlib-prefix.ndjson')
drrun=Path('/workspace/scratch/f55dc021446a/diagnostics/dynamorio/bin64/drrun');client=Path('/workspace/scratch/f55dc021446a/diagnostics/counter-v1.so')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(out/n).write_text(json.dumps(v,indent=2)+'\n')
assert sha(client)=='212a57d6dedc34155467d196e76d30b5d50ceb15010212c4c0f65dd6914194ce'
assert sha(fixture)=='c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
variants={'released-2':('baseline-targeted',2),'stack-2':(a.selected,2),'stack-1':(a.selected,1)}
identities={n:{'binary_sha256':sha(bins/(arm+'.bin')),'checking_workers':t,'arm':arm} for n,(arm,t) in variants.items()}
assert identities['stack-1']['binary_sha256']==identities['stack-2']['binary_sha256']
assert identities['released-2']['binary_sha256']!=identities['stack-2']['binary_sha256']
save('identity.json',{'variants':identities,'input_sha256':sha(fixture),'counter_sha256':sha(client),'boundary':'Same executable for worker comparison; instruction score and wall time are separate. Fixed prefix only.'})
controls=[]
for n in [1,17,1000000]:
 src=out/f'loop-{n}.S';binary=out/f'loop-{n}.bin'
 src.write_text('.global _start\n.text\n_start:\n'+f' movl ${n}, %ecx\n xorl %eax, %eax\n'+'again:\n addl $1, %eax\n decl %ecx\n jnz again\n movl $60, %eax\n xorl %edi, %edi\n syscall\n')
 subprocess.run(['gcc','-nostdlib','-no-pie',str(src),'-o',str(binary)],check=True)
 r=subprocess.run([str(drrun),'-c',str(client),'--',str(binary)],capture_output=True,timeout=30)
 (out/f'loop-{n}.stderr').write_bytes(r.stderr)
 hits=re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',r.stderr)
 count=int(hits[0]) if len(hits)==1 else None
 assert r.returncode==0 and count==3*n+5
 controls.append({'n':n,'expected':3*n+5,'observed':count,'raw_exit':r.returncode})
save('calibration.json',controls)
rows=[]
for instrumented,rounds in [(True,2),(False,4)]:
 kind='instructions' if instrumented else 'native'
 for i in range(rounds):
  names=list(variants)
  for name in names if i%2==0 else reversed(names):
   arm,t=variants[name];binary=bins/(arm+'.bin');assert sha(binary)==identities[name]['binary_sha256']
   cmd=([str(drrun),'-c',str(client),'--'] if instrumented else [])+[str(binary),'--stdin','--threads',str(t),'--nat-extension','--string-extension','--axiom-allow-all']
   tag=f'{kind}-{name}-{i}';start=time.monotonic()
   with fixture.open('rb') as inp,(out/(tag+'.stdout')).open('wb') as stdout,(out/(tag+'.stderr')).open('wb') as stderr:
    proc=subprocess.Popen(cmd,stdin=inp,stdout=stdout,stderr=stderr)
    _,status,usage=os.wait4(proc.pid,0);proc.returncode=os.waitstatus_to_exitcode(status)
   stdout=(out/(tag+'.stdout')).read_bytes();stderr=(out/(tag+'.stderr')).read_bytes()
   row={'variant':name,'round':i,'measurement':kind,'raw_exit':proc.returncode,'wall_s':time.monotonic()-start,'cpu_s':usage.ru_utime+usage.ru_stime,'peak_rss_kib':usage.ru_maxrss,'complete':bool(re.search(rb'checked 25131 declarations',stdout))}
   if instrumented:
    hits=re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',stderr);row['instructions']=int(hits[0]) if len(hits)==1 else None;assert row['instructions'] is not None
   rows.append(row);save('rows.json',rows);print(tag,json.dumps(row),flush=True)
   assert row['raw_exit']==0 and row['complete'],row
   assert sha(binary)==identities[name]['binary_sha256']
results={}
for name in variants:
 results[name]={}
 for base in ['released-2','stack-2']:
  r=[x for x in rows if x['variant']==name and x['measurement']=='instructions'];b=[x for x in rows if x['variant']==base and x['measurement']=='instructions']
  nr=[x for x in rows if x['variant']==name and x['measurement']=='native'];nb=[x for x in rows if x['variant']==base and x['measurement']=='native']
  results[name][base]={'instruction_ratio':sum(x['instructions'] for x in r)/sum(x['instructions'] for x in b),'paired_instruction_ratios':[r[i]['instructions']/b[i]['instructions'] for i in [0,1]],'cpu_ratio':sum(x['cpu_s'] for x in nr)/sum(x['cpu_s'] for x in nb),'wall_ratio':sum(x['wall_s'] for x in nr)/sum(x['wall_s'] for x in nb),'peak_rss_ratio':max(x['peak_rss_kib'] for x in nr)/max(x['peak_rss_kib'] for x in nb)}
save('summary.json',{'results':results,'boundary':'Measured joint source/compiler/worker outcomes on exact prefix; not full Mathlib, native-target hardware instructions or an Arena rank.'})
print('SUMMARY',json.dumps(results),flush=True)
