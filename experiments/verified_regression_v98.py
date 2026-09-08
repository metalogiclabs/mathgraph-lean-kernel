#!/usr/bin/env python3
import difflib, hashlib, json, math, os, shutil, statistics, subprocess, time
from pathlib import Path

BASE='08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA='91f376e4baacf2df0c478e7173bccb2a6adac5c5'
REPO='https://github.com/metalogiclabs/mathgraph-lean-kernel'
SOURCE_BLOB='c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
CORPORA=('std','cedar','mathlib')
ROOT=Path(os.environ.get('V98_ROOT','/tmp/v98')).resolve()

OLD="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
        let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
        let mut n = 0usize;
        let mut out_mask = 0u64;
"""
NEW="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        if let value::Env::Cons { v, parent, .. } = e {
            if let value::Env::Framed { mask: fmask, slots, .. } = *parent {
                let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
                let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
                let mut n = 0usize;
                let mut out_mask = 0u64;
                if mask & 1 != 0 {
                    buf[n].write(*v);
                    slots_hash = slots_hash
                        .wrapping_mul(0x9E3779B97F4A7C15)
                        .wrapping_add(*v as *const Value<'t> as usize as u64);
                    out_mask |= 1;
                    n += 1;
                }
                let rem = mask >> 1;
                let m2 = rem & *fmask & ((1u64 << 63) - 1);
                out_mask |= m2 << 1;
                let mut sel = select_ranks(m2, *fmask);
                while sel != 0 {
                    let i = sel.trailing_zeros() as usize;
                    sel &= sel - 1;
                    let sv = slots[i];
                    buf[n].write(sv);
                    slots_hash = slots_hash
                        .wrapping_mul(0x9E3779B97F4A7C15)
                        .wrapping_add(sv as *const Value<'t> as usize as u64);
                    n += 1;
                }
                let picked: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
                let lsub = e.lsub();
                let hash = out_mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
                let r = self.intern_frame(hash, out_mask, picked, lsub);
                self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
                if let value::Env::Cons { prune, .. } = e { prune.set((mask, Some(r))); }
                return r;
            }
        }
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
        let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
        let mut n = 0usize;
        let mut out_mask = 0u64;
"""

def run(*args,cwd=None,stdin=None,stdout=None,stderr=None):
    return subprocess.run(args,cwd=cwd,stdin=stdin,stdout=stdout,stderr=stderr,check=True)

def shell(script,cwd):
    run('nix','develop','-c','bash','-euo','pipefail','-c',script,cwd=cwd)

def checkout(url,path,sha):
    if not path.exists(): run('git','clone','-q',url,str(path))
    run('git','-C',str(path),'checkout','-q',sha)
    assert subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()==sha

def guarded(path):
    raw=path.read_bytes(); blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(); assert blob==SOURCE_BLOB,(blob,SOURCE_BLOB); return raw.decode()

def apply_candidate(path):
    s=guarded(path); assert s.count(OLD)==1; path.write_text(s.replace(OLD,NEW,1))

def run_binary(binary,config,inp,stdout=None,stderr=None):
    with inp.open('rb') as f: return run(str(binary),str(config),stdin=f,stdout=stdout,stderr=stderr)

def main():
    if ROOT.exists(): shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    control,candidate,arena=ROOT/'control',ROOT/'candidate',ROOT/'arena'
    checkout(REPO,control,BASE); shutil.copytree(control,candidate,ignore=shutil.ignore_patterns('.git','target')); checkout('https://github.com/leanprover/lean-kernel-arena',arena,ARENA)
    apply_candidate(candidate/'src/eval.rs')
    (ROOT/'candidate-diff.txt').write_text(''.join(difflib.unified_diff((control/'src/eval.rs').read_text().splitlines(True),(candidate/'src/eval.rs').read_text().splitlines(True),fromfile='control/src/eval.rs',tofile='candidate/src/eval.rs')))
    print('V98_SOURCE_GUARD=PASS',flush=True)
    config=ROOT/'config.json'; config.write_text(json.dumps(dict(use_stdin=True,nat_extension=True,string_extension=True,unpermitted_axiom_hard_error=False,unsafe_permit_all_axioms=True,num_threads=4,print_success_message=False)))
    for c in CORPORA: shell('./lka.py build-test '+c+' >/dev/null',arena)
    flags="RUSTFLAGS='-C target-cpu=native'"
    for arm in (control,candidate): shell('cd '+str(arm)+' && '+flags+' cargo build --release --locked -q',arena)
    result={'base':BASE,'arena':ARENA,'candidate':'one-cons-over-framed-fastpath','corpora':{}}
    for c in CORPORA:
        inp=arena/'_build/tests'/(c+'.ndjson')
        outs={}
        for arm,name in ((control,'control'),(candidate,'candidate')):
            op,ep=ROOT/(name+'-'+c+'.out'),ROOT/(name+'-'+c+'.err')
            with op.open('wb') as out, ep.open('wb') as err: run_binary(arm/'target/release/sokonanoda',config,inp,out,err)
            outs[name]=(op.read_bytes(),ep.read_bytes())
        assert outs['control']==outs['candidate']==(b'',b'')
        print('V98_'+c.upper()+'_EXACT_REPLAY=PASS',flush=True)
        m={'control':[],'candidate':[]}
        for i in range(7):
            order=((control,'control'),(candidate,'candidate')) if i%2==0 else ((candidate,'candidate'),(control,'control'))
            for arm,name in order:
                t=time.perf_counter(); run_binary(arm/'target/release/sokonanoda',config,inp,subprocess.DEVNULL,subprocess.DEVNULL); m[name].append(time.perf_counter()-t)
        cm,xm=statistics.median(m['control']),statistics.median(m['candidate']); d=(xm/cm-1)*100
        result['corpora'][c]=dict(m,control_median=cm,candidate_median=xm,delta_percent=d)
        print('V98_'+c.upper()+'_DELTA_PERCENT='+f'{d:.6f}',flush=True)
    gm=(math.prod(result['corpora'][c]['candidate_median']/result['corpora'][c]['control_median'] for c in CORPORA)**(1/3)-1)*100
    worst=max(result['corpora'][c]['delta_percent'] for c in CORPORA)
    retain=gm<=-0.50 and worst<=0.50
    result.update(geomean_delta_percent=gm,worst_delta_percent=worst,retain_candidate=retain,decision='RETAIN_FOR_REVIEW' if retain else 'REJECT_OR_MORE_EVIDENCE')
    (ROOT/'results.json').write_text(json.dumps(result,indent=2))
    print('V98_GEOMEAN_DELTA_PERCENT='+f'{gm:.6f}',flush=True); print('V98_WORST_DELTA_PERCENT='+f'{worst:.6f}',flush=True); print('V98_RETAIN_CANDIDATE='+('YES' if retain else 'NO'),flush=True); print('V98_COMPLETE=PASS',flush=True)

if __name__=='__main__': main()
