#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v94
rm -rf "$ROOT" && mkdir -p "$ROOT/out" "$ROOT/profile"
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
print('V94_DIRECT_SOURCE_GUARD=PASS')
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
[ "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA" ]
echo V94_ARENA_PIN=$ARENA
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
for arm in control candidate; do
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native -g' cargo build --release --locked -q)
  cp "$ROOT/$arm/target/release/sokonanoda" "$ROOT/$arm.bin"
done
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/control.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/control-$corpus.out" 2> "$ROOT/out/control-$corpus.err"
  "$ROOT/candidate.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/candidate-$corpus.out" 2> "$ROOT/out/candidate-$corpus.err"
  cmp "$ROOT/out/control-$corpus.out" "$ROOT/out/candidate-$corpus.out"
  cmp "$ROOT/out/control-$corpus.err" "$ROOT/out/candidate-$corpus.err"
  echo "V94_${corpus^^}_EXACT_REPLAY=PASS"
done
python3 - "$ROOT" <<'PY'
import pathlib,subprocess,time,json,statistics,math,sys
r=pathlib.Path(sys.argv[1]); corpora=['std','cedar','mathlib']; res={}
def timed(binpath,inp):
    t=time.perf_counter()
    with inp.open('rb') as f: subprocess.run([str(binpath),str(r/'config.json')],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    return time.perf_counter()-t
for corpus in corpora:
    inp=r/'arena'/'_build'/'tests'/f'{corpus}.ndjson'; c=[]; x=[]
    for i in range(7):
        order=[('control',r/'control.bin',c),('candidate',r/'candidate.bin',x)] if i%2==0 else [('candidate',r/'candidate.bin',x),('control',r/'control.bin',c)]
        for _,b,a in order: a.append(timed(b,inp))
    cm=statistics.median(c); xm=statistics.median(x); d=(xm/cm-1)*100
    res[corpus]={'control':c,'candidate':x,'control_median':cm,'candidate_median':xm,'delta_percent':d}
    print(f'V94_{corpus.upper()}_DELTA_PERCENT={d:.6f}')
gm=(math.prod(1+res[c]['delta_percent']/100 for c in corpora)**(1/3)-1)*100
worst=max(res[c]['delta_percent'] for c in corpora)
retain=gm<=-0.50 and worst<=0.50
print(f'V94_GEOMEAN_DELTA_PERCENT={gm:.6f}'); print(f'V94_WORST_DELTA_PERCENT={worst:.6f}')
print('V94_RETAIN_DIRECT='+('YES' if retain else 'NO'))
res['geomean_delta_percent']=gm; res['worst_delta_percent']=worst; res['retain_direct']=retain
(r/'results.json').write_text(json.dumps(res,indent=2))
PY
# Profile the retained candidate's new cost landscape. Use perf stat always; perf record may be unavailable on hosted runners.
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  perf stat -x, -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses \
    -o "$ROOT/profile/$corpus.perfstat" -- "$ROOT/candidate.bin" "$ROOT/config.json" < "$input" >/dev/null 2>/dev/null || true
  perf record -q -F 499 -g -o "$ROOT/profile/$corpus.perf.data" -- "$ROOT/candidate.bin" "$ROOT/config.json" < "$input" >/dev/null 2>/dev/null || true
  if [ -s "$ROOT/profile/$corpus.perf.data" ]; then
    perf report --stdio --no-children --sort=symbol -i "$ROOT/profile/$corpus.perf.data" > "$ROOT/profile/$corpus.report.txt" 2>/dev/null || true
    grep -E 'prune_env_cold|eval|infer_value|memset|intern_frame|key_env' "$ROOT/profile/$corpus.report.txt" | head -30 > "$ROOT/profile/$corpus.hot.txt" || true
  fi
done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json,re,sys
r=Path(sys.argv[1]); out={}
for c in ['std','cedar','mathlib']:
    hot=r/'profile'/f'{c}.hot.txt'
    out[c]=hot.read_text(errors='ignore').splitlines() if hot.exists() else []
    print('V94_PROFILE_'+c.upper()+'_LINES='+str(len(out[c])))
(r/'residual-profile.json').write_text(json.dumps(out,indent=2))
with (r/'summary.txt').open('w') as f:
    x=json.loads((r/'results.json').read_text())
    for c in ['std','cedar','mathlib']: f.write(f"V94_{c.upper()}_DELTA_PERCENT={x[c]['delta_percent']:.6f}\n")
    f.write(f"V94_GEOMEAN_DELTA_PERCENT={x['geomean_delta_percent']:.6f}\nV94_WORST_DELTA_PERCENT={x['worst_delta_percent']:.6f}\nV94_RETAIN_DIRECT={'YES' if x['retain_direct'] else 'NO'}\n")
PY
