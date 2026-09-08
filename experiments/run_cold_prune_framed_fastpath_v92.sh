#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v92
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/control"
git -C "$ROOT/control" checkout -q "$BASE"
cp -a "$ROOT/control" "$ROOT/candidate"
python3 - "$ROOT/candidate" <<'PY'
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
insert="""    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        // v92: specialize only the separator class discovered prospectively by v91:
        // an existing Framed environment, or exactly one Cons above Framed.
        // All other cold-prune calls fall through unchanged to the generic loop.
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
            if let value::Env::Framed { prune, .. } = e { prune.set((mask, Some(r))); }
            return r;
        }
        if let value::Env::Cons { v, parent, .. } = e {
            if let value::Env::Framed { mask: fmask, slots, .. } = *parent {
                let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
                let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
                let mut n = 0usize;
                let mut out_mask = 0u64;
                let mut rem = mask;
                if rem & 1 != 0 {
                    buf[n].write(*v);
                    slots_hash = slots_hash
                        .wrapping_mul(0x9E3779B97F4A7C15)
                        .wrapping_add(*v as *const Value<'t> as usize as u64);
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
                        slots_hash = slots_hash
                            .wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(sv as *const Value<'t> as usize as u64);
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
s=s.replace(needle,insert,1)
p.write_text(s)
print('V92_SOURCE_GUARD=PASS')
print('V92_CHANGE=FRAMED_OR_ONE_CONS_OVER_FRAMED_COLD_PRUNE_FASTPATH_ONLY')
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo V92_ARENA_PIN=$(git -C "$ROOT/arena" rev-parse HEAD)
[ "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA" ]
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
for arm in control candidate; do
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q)
  cp "$ROOT/$arm/target/release/sokonanoda" "$ROOT/$arm.bin"
done
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/control.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/control-$corpus.out" 2> "$ROOT/out/control-$corpus.err"
  "$ROOT/candidate.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/candidate-$corpus.out" 2> "$ROOT/out/candidate-$corpus.err"
  cmp "$ROOT/out/control-$corpus.out" "$ROOT/out/candidate-$corpus.out"
  cmp "$ROOT/out/control-$corpus.err" "$ROOT/out/candidate-$corpus.err"
  echo "V92_${corpus^^}_EXACT_REPLAY=PASS"
done
python3 - "$ROOT" <<'PY'
import pathlib,subprocess,time,json,statistics,math,sys
r=pathlib.Path(sys.argv[1])
corpora=['std','cedar','mathlib']
res={}
def timed(binpath,inp):
    t=time.perf_counter()
    with inp.open('rb') as f:
        subprocess.run([str(binpath),str(r/'config.json')],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    return time.perf_counter()-t
for corpus in corpora:
    inp=r/'arena'/'_build'/'tests'/f'{corpus}.ndjson'
    c=[]; x=[]
    # five paired alternating passes; alternate order to reduce drift.
    for i in range(5):
        order=[('control',r/'control.bin',c),('candidate',r/'candidate.bin',x)] if i%2==0 else [('candidate',r/'candidate.bin',x),('control',r/'control.bin',c)]
        for _,b,a in order: a.append(timed(b,inp))
    cm=statistics.median(c); xm=statistics.median(x); d=(xm/cm-1)*100
    res[corpus]={'control':c,'candidate':x,'control_median':cm,'candidate_median':xm,'delta_percent':d}
    print(f'V92_{corpus.upper()}_DELTA_PERCENT={d:.6f}')
geomean=(math.prod(1+res[c]['delta_percent']/100 for c in corpora)**(1/3)-1)*100
worst=max(res[c]['delta_percent'] for c in corpora)
print(f'V92_GEOMEAN_DELTA_PERCENT={geomean:.6f}')
print(f'V92_WORST_DELTA_PERCENT={worst:.6f}')
if geomean <= -0.50 and worst <= 0.50:
    decision='PROMOTE_FRAMED_COLD_PRUNE_FASTPATH'
elif geomean < 0:
    decision='SMALL_OR_MIXED_GAIN__DO_NOT_PROMOTE_YET'
else:
    decision='NO_GAIN__REJECT_FASTPATH'
print('DECISION='+decision)
res['geomean_delta_percent']=geomean; res['worst_delta_percent']=worst; res['decision']=decision
(r/'results.json').write_text(json.dumps(res,indent=2))
(r/'summary.txt').write_text('\n'.join([
    *(f"V92_{c.upper()}_DELTA_PERCENT={res[c]['delta_percent']:.6f}" for c in corpora),
    f'V92_GEOMEAN_DELTA_PERCENT={geomean:.6f}',f'V92_WORST_DELTA_PERCENT={worst:.6f}','DECISION='+decision])+'\n')
PY
