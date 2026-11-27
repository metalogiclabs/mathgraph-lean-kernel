"""Qualify the selected frozen executable after all cost measurements finish."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build as b
source=b.WORK/'source';ids=json.loads((b.OUT/'stack-control-source.json').read_text())
assert b.identities(source)==ids
binary=b.BIN/'stack-control.bin';frozen=b.sha(binary)
env=dict(os.environ,CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0',CARGO_TARGET_DIR=str(b.WORK/'target'),RUSTFLAGS=b.FLAGS)
with (b.OUT/'selected-source-tests.log').open('wb') as f:
 r=subprocess.run([os.environ.get('CARGO','/tmp/flash-cargo/bin/cargo'),'test','--release','--locked','--offline','--manifest-path',str(source/'Cargo.toml'),'--target','x86_64-unknown-linux-gnu'],env=env,stdout=f,stderr=subprocess.STDOUT)
assert r.returncode==0,'Preserve test build failure separately'
assert '39 passed; 0 failed' in (b.OUT/'selected-source-tests.log').read_text()
assert b.sha(binary)==frozen and b.identities(source)==ids
results={}
for workers in [1,2]:
 out=b.OUT/f'portable-{workers}'
 with (b.OUT/f'portable-{workers}.log').open('wb') as f:
  r=subprocess.run(['python3',str(Path(__file__).with_name('portable.py')),'portable','--binary',str(binary),'--out',str(out),'--results',str(b.ROOT/'experiments/flash-upstream-repair-20261126/official-inputs.json'),'--fixtures','/tmp/flash-runtime/fixtures'],env=dict(os.environ,STRICT_THREADS=str(workers)),stdout=f,stderr=subprocess.STDOUT)
 results[str(workers)]={'launcher_raw_exit':r.returncode,'summary':json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else None}
 b.save(b.OUT/'selected-qualification.json',{'library_tests':39,'binary_sha256':frozen,'workers':results})
 print('WORKER_QUALIFICATION',workers,json.dumps(results[str(workers)]),flush=True)
 assert b.sha(binary)==frozen and b.identities(source)==ids
assert all(x['launcher_raw_exit']==0 and x['summary']['correct']==230 and x['summary']['attempted']==230 for x in results.values())
