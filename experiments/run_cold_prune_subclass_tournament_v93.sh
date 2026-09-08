#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v93
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/control"
git -C "$ROOT/control" checkout -q "$BASE"
cp -a "$ROOT/control" "$ROOT/direct"
cp -a "$ROOT/control" "$ROOT/onecons"
python3 - "$ROOT/direct" direct <<'PY'
from pathlib import Path
import hashlib,sys
root=Path(sys.argv[1]); mode=sys.argv[2]; p=root/'src/eval.rs'; s=p.read_text()
def blob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
assert blob(p.read_bytes())=='c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
needle="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
"""
assert s.count(needle)==1
fast="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        if let value::Env::Framed { mask: fmask, slots, .. } = e {
            let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
            let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
            let m2 = mask & *fmask;
            let out_mask = m2;
            let mut n = 0usize;
            let mut sel = select_ranks(m2, *fmask);
            while sel != 0 {
                let i = sel.trailing_zeros() as usize;
                sel &= sel - 1;
                let sv = slots[i];
                buf[n].write(sv);
                slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(sv as *const Value<'t> as usize as u64);
                n += 1;
            }
            let picked: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
            let lsub = e.lsub();
            let hash = out_mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
            let r = self.intern_frame(hash, out_mask, picked, lsub);
            self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
            if let value::Env::Framed { prune, .. } = e { prune.set((mask, Some(r))); }
            return r;
        }
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
"""
s=s.replace(needle,fast,1)
p.write_text(s)
print('V93_DIRECT_SOURCE_GUARD=PASS')
PY
python3 - "$ROOT/onecons" onecons <<'PY'
from pathlib import Path
import hashlib,sys
root=Path(sys.argv[1]); p=root/'src/eval.rs'; s=p.read_text()
def blob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
assert blob(p.read_bytes())=='c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
needle="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
"""
assert s.count(needle)==1
fast="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        if let value::Env::Cons { v, parent, .. } = e {
            if let value::Env::Framed { mask: fmask, slots, .. } = *parent {
                let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
                let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
                let mut n = 0usize;
                let mut out_mask = 0u64;
                let mut rem = mask;
                if rem & 1 != 0 {
                    buf[n].write(*v);
                    slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(*v as *const Value<'t> as usize as u64);
                    out_mask |= 1;
                    n += 1;
                }
                rem >>= 1;
                if rem != 0 {
                    let m2 = rem & *fmask & ((1u64 << 63) - 1);
                    out_mask |= m2 << 1;
                    let mut sel = select_ranks(m2, *fmask);
                    while sel != 0 {
                        let i = sel.trailing_zeros() as usize;
                        sel &= sel - 1;
                        let sv = slots[i];
                        buf[n].write(sv);
                        slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(sv as *const Value<'t> as usize as u64);
                        n += 1;
                    }
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
"""
s=s.replace(needle,fast,1)
p.write_text(s)
print('V93_ONECONS_SOURCE_GUARD=PASS')
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
[ "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA" ]
echo V93_ARENA_PIN=$ARENA
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
for arm in control direct onecons; do
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q)
  cp "$ROOT/$arm/target/release/sokonanoda" "$ROOT/$arm.bin"
done
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/control.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/control-$corpus.out" 2> "$ROOT/out/control-$corpus.err"
  for arm in direct onecons; do
    "$ROOT/$arm.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/$arm-$corpus.out" 2> "$ROOT/out/$arm-$corpus.err"
    cmp "$ROOT/out/control-$corpus.out" "$ROOT/out/$arm-$corpus.out"
    cmp "$ROOT/out/control-$corpus.err" "$ROOT/out/$arm-$corpus.err"
    echo "V93_${arm^^}_${corpus^^}_EXACT_REPLAY=PASS"
  done
done
python3 - "$ROOT" <<'PY'
import pathlib,subprocess,time,json,statistics,math,sys
r=pathlib.Path(sys.argv[1]); corpora=['std','cedar','mathlib']; arms=['direct','onecons']; res={a:{} for a in arms}
def timed(binpath,inp):
    t=time.perf_counter()
    with inp.open('rb') as f:
        subprocess.run([str(binpath),str(r/'config.json')],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    return time.perf_counter()-t
for corpus in corpora:
    inp=r/'arena'/'_build'/'tests'/f'{corpus}.ndjson'
    times={'control':[],'direct':[],'onecons':[]}
    for i in range(5):
        order=['control','direct','onecons'] if i%2==0 else ['onecons','direct','control']
        for a in order: times[a].append(timed(r/f'{a}.bin',inp))
    cm=statistics.median(times['control'])
    for a in arms:
        xm=statistics.median(times[a]); d=(xm/cm-1)*100
        res[a][corpus]={'control':times['control'],'candidate':times[a],'control_median':cm,'candidate_median':xm,'delta_percent':d}
        print(f'V93_{a.upper()}_{corpus.upper()}_DELTA_PERCENT={d:.6f}')
for a in arms:
    gm=(math.prod(1+res[a][c]['delta_percent']/100 for c in corpora)**(1/3)-1)*100
    worst=max(res[a][c]['delta_percent'] for c in corpora)
    res[a]['geomean_delta_percent']=gm; res[a]['worst_delta_percent']=worst
    print(f'V93_{a.upper()}_GEOMEAN_DELTA_PERCENT={gm:.6f}')
    print(f'V93_{a.upper()}_WORST_DELTA_PERCENT={worst:.6f}')
eligible=[a for a in arms if res[a]['geomean_delta_percent'] <= -0.50 and res[a]['worst_delta_percent'] <= 0.50]
if eligible:
    winner=min(eligible,key=lambda a:res[a]['geomean_delta_percent'])
    decision='PROMOTE_'+winner.upper()+'_ONLY'
else:
    better=min(arms,key=lambda a:res[a]['geomean_delta_percent'])
    decision='NO_SUBCLASS_PROMOTION__NEXT_RESIDUAL='+better.upper()
print('DECISION='+decision)
res['decision']=decision
(r/'results.json').write_text(json.dumps(res,indent=2))
(r/'summary.txt').write_text('\n'.join([*(f"V93_{a.upper()}_{c.upper()}_DELTA_PERCENT={res[a][c]['delta_percent']:.6f}" for a in arms for c in corpora),*(f"V93_{a.upper()}_GEOMEAN_DELTA_PERCENT={res[a]['geomean_delta_percent']:.6f}" for a in arms),*(f"V93_{a.upper()}_WORST_DELTA_PERCENT={res[a]['worst_delta_percent']:.6f}" for a in arms),'DECISION='+decision])+'\n')
PY
