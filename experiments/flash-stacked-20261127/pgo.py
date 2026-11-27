"""Fresh Init-only training for one measured source combination."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build as b
p=argparse.ArgumentParser();p.add_argument('--parent',choices=list(b.ARMS),required=True);a=p.parse_args()
features=b.ARMS[a.parent]
host='x86_64-unknown-linux-gnu'
training=b.WORK/'training';raw=training/'raw';raw.mkdir(exist_ok=False)
fixture=training/'init.ndjson'
assert fixture.stat().st_size==348430202
assert b.sha(fixture)=='e819664a1c7d7df8dc303077a9f85be2a1d24bc60d57636b64570edff83e5724'
# Both ordinary controls use the same explicit target as profile generation/use.
b.build('baseline-targeted',{},target=host)
b.build('stack-control',features,target=host)
generate=' -C profile-generate='+str(raw)+' -C llvm-args=-instrprof-atomic-counter-update-all'
binary=b.build('instrumented',features,extra_flags=generate,target=host)
assert not list(raw.glob('*.profraw')),'Host build profiles must not enter training'
rows=[]
for threads in [1,2]:
 env=dict(os.environ,LLVM_PROFILE_FILE=str(raw/'stack-%p-%m.profraw'))
 with fixture.open('rb') as inp:
  r=subprocess.run([str(binary),'--stdin','--threads',str(threads),'--nat-extension','--string-extension','--axiom-allow-all'],env=env,stdin=inp,capture_output=True,timeout=240)
 (b.OUT/f'training-{threads}.stdout').write_bytes(r.stdout)
 (b.OUT/f'training-{threads}.stderr').write_bytes(r.stderr)
 match=re.search(rb'checked (\d+) declarations',r.stdout)
 count=int(match.group(1)) if match else None
 rows.append({'threads':threads,'raw_exit':r.returncode,'declarations':count})
 assert r.returncode==0 and count==59626,rows[-1]
profiles=sorted(raw.glob('*.profraw'));assert profiles
sysroot=Path(subprocess.check_output([os.environ.get('RUSTC','/tmp/flash-cargo/bin/rustc'),'--print','sysroot'],text=True).strip())
tool=sysroot/'lib/rustlib'/host/'bin/llvm-profdata'
profile=training/'stack.profdata'
subprocess.run([str(tool),'merge','-sparse',*[str(x) for x in profiles],'-o',str(profile)],check=True)
with profile.open('rb') as inp,gzip.open(b.OUT/'training.profdata.gz','wb') as out:
 while block:=inp.read(1048576):out.write(block)
identity={'parent':a.parent,'features':features,'input_sha256':b.sha(fixture),'input_bytes':fixture.stat().st_size,'data_url':'https://github.com/sdiehl/nano-lean/releases/download/pgo-data-1/init.ndjson.gz','gzip_sha256':'be43e8fc8fa3f9212f6bf005a924834af5cbfdb2ec6b7524fc85efbaf5c6a76e','executions':rows,'raw_profiles':{x.name:{'sha256':b.sha(x),'bytes':x.stat().st_size} for x in profiles},'merged_profile_sha256':b.sha(profile),'instrumented_binary_sha256':b.sha(binary),'boundary':'Init-only compiler training; mathematical foundation overlap with Mathlib. No benchmark measurement or Mathlib execution used for training.'}
b.save(b.OUT/'training.json',identity)
use=' -C profile-use='+str(profile)+' -C llvm-args=-pgo-warn-missing-function'
b.build('stack-pgo',features,extra_flags=use,target=host)
log=(b.OUT/'stack-pgo-build.log').read_text(errors='replace')
bad=[line for line in log.splitlines() if re.search(r'hash mismatch|mismatched|out.of.date profile',line,re.I)]
b.save(b.OUT/'profile-check.json',{'profile_mismatch_lines':bad,'warnings':[x for x in log.splitlines() if 'warning:' in x],'boundary':'Missing coverage for unexecuted functions is distinct from a profile hash mismatch.'})
assert not bad,bad
print('PGO_SOURCE_READY',a.parent,flush=True)
