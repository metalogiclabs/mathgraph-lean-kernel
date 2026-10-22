import hashlib,json,os,subprocess,time
from pathlib import Path
repo=Path('/workspace/mathgraph-lean-kernel-lifecycle')
out=Path(__file__).resolve().parent
source='cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain','--','src','Cargo.toml','Cargo.lock'],cwd=repo,text=True).strip()
files=[Path('Cargo.toml'),Path('Cargo.lock')]+sorted(Path(x) for x in subprocess.check_output(['git','ls-files','src'],cwd=repo,text=True).splitlines())
def closure():return {str(p):hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in files}
before=closure()
env=os.environ.copy();env['PATH']='/home/agent/.cargo/bin:'+env['PATH']
versions={name:subprocess.check_output([name,'+1.95.0','--version'],env=env,text=True).strip() for name in ('cargo','rustc')}
command=['cargo','+1.95.0','build','--release','--locked','--target-dir',str(out/'target'),'--bin','sokonanoda','--bin','export-index']
start=time.time()
with (out/'build.log').open('xb') as log:r=subprocess.run(command,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
proof=dict(source_sha=source,source_before=before,source_after=closure(),versions=versions,command=command,returncode=r.returncode,started_unix=start,finished_unix=time.time())
assert r.returncode==0
assert proof['source_before']==proof['source_after']
proof['binary_sha256']={name:hashlib.sha256((out/'target/release'/name).read_bytes()).hexdigest() for name in ('sokonanoda','export-index')}
proof['passed']=True
(out/'build-proof.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
print(json.dumps({'passed':True,'source_sha':source,'binary_sha256':proof['binary_sha256']}))
