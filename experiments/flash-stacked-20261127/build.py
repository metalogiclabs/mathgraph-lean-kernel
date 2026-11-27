"""Build a prospective combination matrix using one controlled source path."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(os.environ.get('FLASH_STACK_WORK','/tmp/flash-stack-work'))
OUT=WORK/'evidence'; OUT.mkdir(parents=True,exist_ok=True)
BIN=OUT/'builds'; BIN.mkdir(exist_ok=True)
BASE='bc704eebed4e009bc66af1a849f18315c11f1926'
FLAGS=os.environ.get('FLASH_STACK_RUSTFLAGS','-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma')
ARMS={'baseline':{},'projection':{'projection':True},
 'pi':{'projection':True,'inline':True},
 'pic':{'projection':True,'inline':True,'chunk':512},
 'pib18':{'projection':True,'inline':True,'budget':18},
 'pib36':{'projection':True,'inline':True,'budget':36},
 'picb36':{'projection':True,'inline':True,'chunk':512,'budget':36}}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def replace(p,a,b):
 s=p.read_text();assert s.count(a)==1,(p,a,s.count(a));p.write_text(s.replace(a,b))
def identities(p):return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file()}
def restore():
 base=WORK/'base';source=WORK/'source'
 if not base.exists():
  base.mkdir();archive=WORK/'base.tar'
  with archive.open('wb') as f:subprocess.run(['git','archive',BASE,'src','Cargo.toml','Cargo.lock','tests','test_resources'],cwd=ROOT,stdout=f,check=True)
  with tarfile.open(archive) as t:t.extractall(base,filter='data')
  archive.unlink()
 source.mkdir(exist_ok=True)
 shutil.copytree(base,source,dirs_exist_ok=True)
 return base,source
def configure(source,features):
 if features.get('projection'):replace(source/'src/checker/infer.rs','        let key = (self.prune_env(env, node.mask), e);','        let env = self.prune_env(env, node.mask);\n        let key = (env, e);')
 if features.get('inline'):replace(source/'src/checker/eval.rs','    fn eval_node(&mut self,','    #[inline(always)]\n    fn eval_node(&mut self,')
 if features.get('chunk'):replace(source/'src/checker/tc.rs','const CHUNK_SIZE: usize = 64;',f'const CHUNK_SIZE: usize = {features["chunk"]};')
 if features.get('budget'):replace(source/'src/checker/cache.rs','pub(crate) const SESSION_BUDGET: usize = 9 * 1024 * 1024;',f'pub(crate) const SESSION_BUDGET: usize = {features["budget"]} * 1024 * 1024;')
def build(arm,features,extra_flags='',target=None,tests=False):
 base,source=restore();configure(source,features);before=identities(source)
 save(OUT/(arm+'-source.json'),before)
 patch=[]
 for name in before:
  if (base/name).read_bytes()!=(source/name).read_bytes():
   patch.extend(difflib.unified_diff((base/name).read_text().splitlines(True),(source/name).read_text().splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 (OUT/(arm+'.patch')).write_text(''.join(patch))
 env=dict(os.environ,CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0',
          CARGO_TARGET_DIR=str(WORK/'target'),RUSTFLAGS=FLAGS+extra_flags)
 cargo=os.environ.get('CARGO','/tmp/flash-cargo/bin/cargo')
 command=[cargo,'build','--release','--locked','--manifest-path',str(source/'Cargo.toml')]
 if os.environ.get('FLASH_STACK_OFFLINE','1')=='1':command+=['--offline']
 if target:command+=['--target',target]
 with (OUT/(arm+'-build.log')).open('wb') as f:subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 assert identities(source)==before,'Source changed during build'
 binary=BIN/(arm+'.bin');built=WORK/'target'
 if target:built/=target
 built/='release/sokonanoda'
 shutil.copyfile(built,binary);binary.chmod(0o555)
 row={'arm':arm,'features':features,'binary_sha256':sha(binary),'flags':env['RUSTFLAGS'],'cargo_target':target,'source_identity':arm+'-source.json'}
 rows=json.loads((OUT/'builds.json').read_text()) if (OUT/'builds.json').exists() else []
 assert not any(r['arm']==arm for r in rows),'Frozen build already exists'
 rows.append(row);save(OUT/'builds.json',rows)
 if arm!='instrumented':
  subprocess.run(['python3',str(ROOT/'experiments/flash-upstream-repair-20261126/metadata_controls.py'),'--binary',str(binary),'--out',str(OUT/(arm+'-source-controls'))],check=True)
 if tests:
  command=[cargo,'test','--release','--locked','--manifest-path',str(source/'Cargo.toml')]
  if os.environ.get('FLASH_STACK_OFFLINE','1')=='1':command+=['--offline']
  if target:command+=['--target',target]
  with (OUT/(arm+'-tests.log')).open('wb') as f:subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 assert sha(binary)==row['binary_sha256']
 print('FROZEN',json.dumps(row),flush=True)
 return binary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arms',default=','.join(ARMS));a=p.parse_args()
 save(OUT/'harness.json',{'base':BASE,'arms':ARMS,'flags':FLAGS,'source_path':str(WORK/'source'),'compiler':subprocess.check_output([os.environ.get('RUSTC','/tmp/flash-cargo/bin/rustc'),'-Vv'],text=True),'harness_sha256':sha(Path(__file__))})
 for arm in a.arms.split(','):build(arm,ARMS[arm])
