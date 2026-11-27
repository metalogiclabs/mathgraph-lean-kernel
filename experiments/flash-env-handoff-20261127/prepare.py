"""Create independent source trees, observation build and frozen executables."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = 'bc704eebed4e009bc66af1a849f18315c11f1926'
WORK = Path(os.environ.get('FLASH_HANDOFF_WORK', '/tmp/flash-handoff-work'))
OUT = WORK / 'evidence'
OUT.mkdir(parents=True, exist_ok=True)
BIN = OUT / 'builds'
BIN.mkdir(exist_ok=True)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, x): p.write_text(json.dumps(x, indent=2) + '\n')
def change(p, old, new):
    s = p.read_text()
    assert s.count(old) == 1, (p, old, s.count(old))
    p.write_text(s.replace(old, new))

def source(arm):
    dest = WORK / ('source-' + arm)
    dest.mkdir(exist_ok=False)
    archive = WORK / ('source-' + arm + '.tar')
    with archive.open('wb') as f:
        subprocess.run(['git', 'archive', BASE, 'src', 'Cargo.toml', 'Cargo.lock',
                        'tests', 'test_resources'], cwd=ROOT, stdout=f, check=True)
    with tarfile.open(archive) as t: t.extractall(dest, filter='data')
    archive.unlink()
    return dest

def projection(dest):
    change(dest / 'src/checker/infer.rs',
           '        let key = (self.prune_env(env, node.mask), e);',
           '        let env = self.prune_env(env, node.mask);\n        let key = (env, e);')

def frame_copy(dest):
    p = dest / 'src/checker/eval/environment.rs'
    s = p.read_text()
    start = s.index('                    let mut sel = m2;')
    end = s.index('                    if taken < cut {', start)
    old = s[start:end]
    new = '''                    if m2 == fmask & ((1u64 << taken) - 1) {
                        let end = fstart + m2.count_ones() as usize;
                        for index in fstart..end {
                            let sv = self.vals().env_slot(index);
                            self.vals_mut().push_env_slot(sv);
                            slots_hash = slots_hash
                                .wrapping_mul(GOLDEN)
                                .wrapping_add(u64::from(sv.raw()));
                        }
                    } else {
'''+ ''.join('    '+line+'\n' for line in old.splitlines())+'''                    }
'''
    change(p, old, new)

def census(dest):
    p = dest / 'src/checker/mod.rs'
    p.write_text(p.read_text() + '\npub(crate) mod handoff_census;\n')
    shutil.copyfile(Path(__file__).with_name('census.rs'), dest/'src/checker/handoff_census.rs')
    p=dest/'src/checker/eval/environment.rs'
    s=p.read_text()
    s=s.replace('        if mask == 0 {', '        super::super::handoff_census::inc("prune_calls");\n        if mask == 0 {\n            super::super::handoff_census::inc("zero_mask");',1)
    s=s.replace('        if self.vals().env_is_pruned(e, mask) {', '        if self.vals().env_is_pruned(e, mask) {\n            super::super::handoff_census::inc("already_pruned");',1)
    s=s.replace('        if k == e && m == mask {', '        if k == e && m == mask {\n            super::super::handoff_census::inc("direct_memo_hit");',1)
    s=s.replace('        self.prune_env_cold(e, mask, slot)', '        super::super::handoff_census::cold(e.raw(), mask);\n        self.prune_env_cold(e, mask, slot)',1)
    s=s.replace('                    out_mask |= m2 << consumed;', '                    out_mask |= m2 << consumed;\n                    super::super::handoff_census::frame(m2 == fmask & ((1u64 << taken) - 1), m2.count_ones());',1)
    s=s.replace('        if !fresh {', '        super::super::handoff_census::inc(if fresh {"fresh_frame"} else {"reused_frame"});\n        if !fresh {',1)
    p.write_text(s)
    p=dest/'src/checker/infer.rs'
    change(p, '        let key = (self.prune_env(env, node.mask), e);',
      '        let key = (self.prune_env(env, node.mask), e);\n        super::handoff_census::inc(if key.0 == env {"infer_projection_same"} else {"infer_projection_changed"});')
    p=dest/'src/checker/tc.rs'
    change(p,'            cache.clear_session();','            super::handoff_census::epoch();\n            cache.clear_session();')
    change(p,'            if finished {\n                return;','            if finished {\n                super::handoff_census::finish();\n                return;')

rows=json.loads((OUT/'builds.json').read_text()) if (OUT/'builds.json').exists() else []
for arm in os.environ.get('FLASH_HANDOFF_ARMS','baseline,projection,frame-copy,combined,census').split(','):
    dest=source(arm)
    if arm in ('projection','combined'): projection(dest)
    if arm in ('frame-copy','combined'): frame_copy(dest)
    if arm=='census': census(dest)
    identities={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    save(OUT/(arm+'-source.json'),identities)
    if arm!='baseline':
        lines=[]
        for name in identities:
            old=WORK/'source-baseline'/name
            new=dest/name
            if old.exists() and old.read_bytes()!=new.read_bytes():
                lines.extend(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='a/'+name,tofile='b/'+name))
        (OUT/(arm+'.patch')).write_text(''.join(lines))
    env=dict(os.environ, CARGO_BUILD_JOBS='1', CARGO_INCREMENTAL='0',
             CARGO_TARGET_DIR=str(WORK/'target'),
             RUSTFLAGS=os.environ.get('RUSTFLAGS','-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'))
    cargo=os.environ.get('CARGO','cargo')
    command=[cargo,'build','--release','--locked','--manifest-path',str(dest/'Cargo.toml')]
    with (OUT/(arm+'-build.log')).open('wb') as f:
        subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    binary=BIN/(arm+'.bin'); shutil.copyfile(WORK/'target/release/sokonanoda',binary);binary.chmod(0o555)
    assert not any(r['arm']==arm for r in rows), 'Keep existing frozen-arm evidence'
    rows.append({'arm':arm,'binary_sha256':sha(binary),'source_identity':arm+'-source.json'})
    save(OUT/'builds.json',rows)
    print('FROZEN',json.dumps(rows[-1]),flush=True)
    if arm not in ('baseline','census') and os.environ.get('FLASH_HANDOFF_RUN_TESTS','1')=='1':
        with (OUT/(arm+'-tests.log')).open('wb') as f:
            subprocess.run([cargo,'test','--release','--locked','--manifest-path',str(dest/'Cargo.toml')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        subprocess.run(['python3',str(ROOT/'experiments/flash-upstream-repair-20261126/metadata_controls.py'),'--binary',str(binary),'--out',str(OUT/(arm+'-source-controls'))],check=True)
    assert sha(binary)==rows[-1]['binary_sha256']
save(OUT/'harness.json',{'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'base':BASE,'compiler':subprocess.check_output([os.environ.get('RUSTC','rustc'),'-Vv'],text=True),'flags':env['RUSTFLAGS']})
