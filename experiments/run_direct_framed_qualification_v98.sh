#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v98
HERE=$(pwd)
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/control"
git -C "$ROOT/control" checkout -q "$BASE"
cp -a "$ROOT/control" "$ROOT/candidate"
# Restore the now-qualified negative fixtures into both frozen siblings so tests execute.
for arm in control candidate; do
  cp -a "$HERE/test_resources/RuleDomainMismatch" "$ROOT/$arm/test_resources/"
  cp -a "$HERE/test_resources/UnlistedRecursor" "$ROOT/$arm/test_resources/"
done
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
assert s.count(needle)==1
p.write_text(s.replace(needle,fast,1))
print('V98_SOURCE_GUARD=PASS')
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
[ "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA" ]
echo V98_ARENA_PIN=$ARENA
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
for arm in control candidate; do
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo test --release --locked -q)
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo test --locked -q)
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q)
done
echo V98_RUST_SUITES=PASS
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  for arm in control candidate; do
    "$ROOT/$arm/target/release/sokonanoda" "$ROOT/config.json" < "$input" > "$ROOT/out/$arm-$corpus.out" 2> "$ROOT/out/$arm-$corpus.err"
  done
  cmp "$ROOT/out/control-$corpus.out" "$ROOT/out/candidate-$corpus.out"
  cmp "$ROOT/out/control-$corpus.err" "$ROOT/out/candidate-$corpus.err"
  [ ! -s "$ROOT/out/control-$corpus.out" ] && [ ! -s "$ROOT/out/control-$corpus.err" ]
  echo "V98_${corpus^^}_EXACT_REPLAY=PASS"
done
python3 - "$ROOT" <<'PY'
import pathlib,subprocess,time,json,statistics,math,sys
r=pathlib.Path(sys.argv[1]); corpora=['std','cedar','mathlib']; res={}
def timed(binpath,inp):
    t=time.perf_counter()
    with inp.open('rb') as f: subprocess.run([str(binpath),str(r/'config.json')],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    return time.perf_counter()-t
for corpus in corpora:
    inp=r/'arena'/'_build'/'tests'/f'{corpus}.ndjson'; c=[]; x=[]; paired=[]
    for i in range(9):
        order=['control','candidate'] if i%2==0 else ['candidate','control']
        round_times={}
        for a in order:
            v=timed(r/a/'target/release/sokonanoda',inp); round_times[a]=v
            (c if a=='control' else x).append(v)
        paired.append((round_times['candidate']/round_times['control']-1)*100)
    cm=statistics.median(c); xm=statistics.median(x)
    median_ratio=(xm/cm-1)*100; paired_med=statistics.median(paired)
    res[corpus]={'control':c,'candidate':x,'paired_delta_percent':paired,
                 'control_median':cm,'candidate_median':xm,
                 'median_ratio_delta_percent':median_ratio,'paired_median_delta_percent':paired_med}
    print(f'V98_{corpus.upper()}_MEDIAN_RATIO_DELTA_PERCENT={median_ratio:.6f}')
    print(f'V98_{corpus.upper()}_PAIRED_MEDIAN_DELTA_PERCENT={paired_med:.6f}')
gm=(math.prod(1+res[c]['paired_median_delta_percent']/100 for c in corpora)**(1/3)-1)*100
worst=max(res[c]['paired_median_delta_percent'] for c in corpora)
retain=gm<=-0.50 and worst<=0.50
res.update(base='08ddb26718c86213262943ca19ae8cf1b03fa922',arena='91f376e4baacf2df0c478e7173bccb2a6adac5c5',
           candidate='direct-framed-prune-fast-path',geomean_paired_delta_percent=gm,
           worst_paired_delta_percent=worst,retain_candidate=retain,
           decision='RETAIN_FOR_REVIEW' if retain else 'REJECT_OR_MORE_EVIDENCE')
(r/'results.json').write_text(json.dumps(res,indent=2))
print(f'V98_GEOMEAN_PAIRED_DELTA_PERCENT={gm:.6f}')
print(f'V98_WORST_PAIRED_DELTA_PERCENT={worst:.6f}')
print('V98_RETAIN_CANDIDATE='+('YES' if retain else 'NO'))
print('V98_COMPLETE=PASS')
PY
