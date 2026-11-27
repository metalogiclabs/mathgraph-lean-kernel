"""Reconstruct the selected stack for native and generic full-input gates."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build as b
decision=json.loads(Path(__file__).with_name('decision.json').read_text())
parent=decision['selected_source_arm'];use_pgo=decision['selected_pgo']
features=b.ARMS[parent]
host='x86_64-unknown-linux-gnu'
b.save(b.OUT/'harness.json',{'harness_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=b.ROOT,text=True).strip(),'source_commit':decision['source_commit'],'compiler':subprocess.check_output([os.environ.get('RUSTC','rustc'),'-Vv'],text=True),'flags':b.FLAGS,'checking_workers':{'baseline':2,'strict':int(os.environ.get('STRICT_THREADS','2'))},'cpu':subprocess.check_output(['lscpu'],text=True)})
if use_pgo:
 training=b.WORK/'training';training.mkdir(exist_ok=True)
 archive=training/'init.ndjson.gz'
 urllib.request.urlretrieve('https://github.com/sdiehl/nano-lean/releases/download/pgo-data-1/init.ndjson.gz',archive)
 assert b.sha(archive)=='be43e8fc8fa3f9212f6bf005a924834af5cbfdb2ec6b7524fc85efbaf5c6a76e'
 with gzip.open(archive,'rb') as inp,(training/'init.ndjson').open('wb') as out:shutil.copyfileobj(inp,out)
 subprocess.run(['python3',str(Path(__file__).with_name('pgo.py')),'--parent',parent],check=True)
 selected='stack-pgo'
else:
 b.build('baseline-targeted',{},target=host)
 b.build('stack-control',features,target=host)
 selected='stack-control'
for name,arm in [('baseline','baseline-targeted'),('strict',selected)]:
 shutil.copyfile(b.BIN/(arm+'.bin'),b.BIN/(name+'.bin'));(b.BIN/(name+'.bin')).chmod(0o555)
assert b.identities(b.WORK/'source')==decision['source_identity'],'Generated source must match the declared measured candidate'
if os.environ.get('MODE')=='native':
 # Preserve the actual comparison executable before compiling test harnesses.
 before=b.sha(b.BIN/'strict.bin');source=b.WORK/'source'
 row=next(x for x in json.loads((b.OUT/'builds.json').read_text()) if x['arm']==selected)
 assert b.identities(source)==json.loads((b.OUT/(selected+'-source.json')).read_text())
 env=dict(os.environ,CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0',CARGO_TARGET_DIR=str(b.WORK/'target'),RUSTFLAGS=row['flags'])
 with (b.OUT/'source-tests.log').open('wb') as f:
  subprocess.run([os.environ.get('CARGO','cargo'),'test','--release','--locked','--manifest-path',str(source/'Cargo.toml'),'--target',host],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 assert b.sha(b.BIN/'strict.bin')==before
b.save(b.OUT/'selected-source.json',{'arm':selected,'features':features,'source_identity':selected+'-source.json','binary_sha256':b.sha(b.BIN/'strict.bin'),'baseline_sha256':b.sha(b.BIN/'baseline.bin'),'source_comparison':decision['source_commit'],'checking_workers':{'baseline':2,'strict':int(os.environ.get('STRICT_THREADS','2'))},'build_boundary':'Fresh matched target flags and source; training, when selected, repeats only Init input.'})
