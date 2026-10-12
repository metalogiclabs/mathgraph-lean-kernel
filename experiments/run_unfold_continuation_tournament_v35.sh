#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARMS=(base same1 same4)
rm -rf /tmp/v35-* /tmp/v35-arena

for arm in "${ARMS[@]}"; do
  git worktree add "/tmp/v35-$arm" "$BASE"
  python3 - "$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]
# Verified v29 wall-time seed: Pi-only force collapse in every arm.
p=Path(f'/tmp/v35-{arm}/src/eval.rs'); s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

if arm == 'base':
    raise SystemExit

p=Path(f'/tmp/v35-{arm}/src/conv.rs'); s=p.read_text()
old=r'''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {
        let v1 = self.unfold_value(depth, t);
        let v2 = self.unfold_value(depth, t2);
        if std::ptr::eq(v1, t) && std::ptr::eq(v2, t2) {
            let f1 = self.unfold_value_demand(depth, t);
            let f2 = self.unfold_value_demand(depth, t2);
            if std::ptr::eq(f1, t) && std::ptr::eq(f2, t2) {
                return false;
            }
            return self.unify::<true>(depth, f1, f2);
        }
        self.unify::<true>(depth, v1, v2)
    }'''
assert s.count(old)==1
limit = 1 if arm == 'same1' else 4
new=f'''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {{
        let mut a = t;
        let mut b = t2;
        let mut fused = 0u32;
        loop {{
            let v1 = self.unfold_value(depth, a);
            let v2 = self.unfold_value(depth, b);
            if std::ptr::eq(v1, a) && std::ptr::eq(v2, b) {{
                let f1 = self.unfold_value_demand(depth, a);
                let f2 = self.unfold_value_demand(depth, b);
                if std::ptr::eq(f1, a) && std::ptr::eq(f2, b) {{
                    return false;
                }}
                return self.unify::<true>(depth, f1, f2);
            }}
            // Preserve the first consequence that generic unify would observe.
            if std::ptr::eq(v1, v2) {{
                return true;
            }}
            if fused >= {limit} {{
                return self.unify::<true>(depth, v1, v2);
            }}
            match (v1, v2) {{
                (
                    Value::Unfold {{ head: UnfoldHead {{ name: nx, levels: lx }}, spine: sx, .. }},
                    Value::Unfold {{ head: UnfoldHead {{ name: ny, levels: ly }}, spine: sy, .. }},
                ) if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {{
                    let nx = *nx;
                    let lx = *lx;
                    let sx = *sx;
                    let sy = *sy;
                    let (sig, lim) = self.head_spine_sig(nx, lx, sx, sy);
                    // These are exactly the native same-head checks performed before unfold_pair.
                    if self.spine_probe(depth, sx, sy, sig, lim) {{
                        return true;
                    }}
                    if self.try_proof_irrel_at(depth, v1, v2) {{
                        return true;
                    }}
                    a = v1;
                    b = v2;
                    fused += 1;
                    continue;
                }}
                _ => return self.unify::<true>(depth, v1, v2),
            }}
        }}
    }}'''
p.write_text(s.replace(old,new,1))
PY
done

cat >/tmp/v35-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in "${ARMS[@]}"; do
  (cd "/tmp/v35-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v35-$arm/target/release/sokonanoda" "/tmp/v35-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v35-arena
cd /tmp/v35-arena
for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done

# Exact differential gate before timing.
for t in std cedar; do
  /tmp/v35-base-bin /tmp/v35-config.json < "_build/tests/$t.ndjson" >"/tmp/v35-$t-base.out" 2>"/tmp/v35-$t-base.err"
  for arm in same1 same4; do
    /tmp/v35-$arm-bin /tmp/v35-config.json < "_build/tests/$t.ndjson" >"/tmp/v35-$t-$arm.out" 2>"/tmp/v35-$t-$arm.err"
    cmp "/tmp/v35-$t-base.out" "/tmp/v35-$t-$arm.out"
    echo "V35_${t^^}_${arm^^}_SEMANTIC_REPLAY=EXACT"
  done
done

# Alternating measurements: every arm occupies each order position across rounds.
rm -f /tmp/v35-*.time
for t in std cedar; do
  orders=("base same1 same4" "same1 same4 base" "same4 base same1")
  r=0
  for order in "${orders[@]}"; do
    r=$((r+1))
    for arm in $order; do
      /usr/bin/time -f '%e %U %S %M' -o "/tmp/v35-${t}-${arm}-${r}.time" \
        "/tmp/v35-$arm-bin" /tmp/v35-config.json < "_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v35-${t}-${arm}-${r}.err"
    done
  done
done

python3 - <<'PY' | tee /tmp/v35-decision.txt
from pathlib import Path
from statistics import median
arms=['base','same1','same4']; tests=['std','cedar']
vals={}
for t in tests:
    vals[t]={}
    for a in arms:
        xs=[]
        for p in sorted(Path('/tmp').glob(f'v35-{t}-{a}-*.time')):
            xs.append(float(p.read_text().split()[0]))
        assert len(xs)==3,(t,a,xs)
        vals[t][a]=median(xs)
        print(f'V35_TIMES {t} {a} raw={xs} median={vals[t][a]:.3f}')
score={}
for a in arms[1:]:
    ds=[]
    for t in tests:
        d=(vals[t][a]/vals[t]['base']-1.0)*100
        ds.append(d)
        print(f'V35_DELTA {t} {a}={d:+.4f}%')
    score[a]=sum(ds)/len(ds)
    print(f'V35_MEAN_NORMALIZED {a}={score[a]:+.4f}%')
winner=min(score,key=score.get)
d=score[winner]
print('V35_TOURNAMENT_WINNER='+winner)
print(f'V35_WINNER_MEAN_NORMALIZED={d:+.4f}%')
if d <= -2.0:
    print('DECISION=V35_ADVANCE_WINNER_TO_FULL_MATHLIB_PGO_GATE')
elif d < 0:
    print('DECISION=V35_WEAK_POSITIVE__RETAIN_AND_MEASURE_MATHLIB_EXPOSURE')
else:
    print('DECISION=V35_KILL_SAME_HEAD_CONTINUATION_FUSION__ROUTE_UNEQUAL_HINT_CONTINUATION')
print('V35_RULE=FUSE_ONLY_VERIFIED_NATIVE_CONTINUATION__NO_NEW_CACHE_OR_REPRESENTATION')
PY
