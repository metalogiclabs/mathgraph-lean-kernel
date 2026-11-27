"""Match the unresolved stress input against unchanged and candidate binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

p=argparse.ArgumentParser();p.add_argument('--arms',default='baseline-targeted,stack-control');p.add_argument('--name',default='stress-control');a=p.parse_args()
root=Path('/tmp/flash-stack-work/evidence');out=root/a.name;out.mkdir(exist_ok=False)
fixture=Path('/tmp/flash-runtime/fixtures/perf/magma-list-pair-n21.ndjson')
assert hashlib.sha256(fixture.read_bytes()).hexdigest()=='36895459051bfb2494aa6a5c8542b36581c74f03a5cbe59282874e2068a47a32'
rows=[]
for arm in a.arms.split(','):
 binary=root/'builds'/(arm+'.bin');before=hashlib.sha256(binary.read_bytes()).hexdigest();start=time.monotonic();expired=[]
 with fixture.open('rb') as inp,(out/(arm+'.stdout')).open('wb') as stdout,(out/(arm+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen([str(binary),'--stdin','--threads','1','--nat-extension','--string-extension','--axiom-allow-all'],stdin=inp,stdout=stdout,stderr=stderr,start_new_session=True)
  def stop():
   expired.append(True)
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  timer=threading.Timer(180,stop);timer.start()
  try:_,status,usage=os.wait4(proc.pid,0);proc.returncode=os.waitstatus_to_exitcode(status)
  finally:timer.cancel()
 row={'arm':arm,'binary_sha256':before,'checking_workers':1,'raw_exit':proc.returncode,'timed_out':bool(expired),'wall_s':time.monotonic()-start,'cpu_s':usage.ru_utime+usage.ru_stime,'max_rss_kib':usage.ru_maxrss,'classification':'ACCEPT' if proc.returncode==0 else 'UNKNOWN_PROCESS_FAILURE' if proc.returncode<0 else 'SEMANTIC_REJECT' if proc.returncode==1 else 'UNKNOWN_INTERNAL_ERROR'}
 rows.append(row);(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
 assert hashlib.sha256(binary.read_bytes()).hexdigest()==before
