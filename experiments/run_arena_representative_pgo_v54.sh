#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v54-current /tmp/v54-rep /tmp/v54-arena /tmp/v54-current-pgo /tmp/v54-rep-pgo /tmp/v54-*.time /tmp/v54-*.out /tmp/v54-*.err
for arm in current rep; do git worktree add "/tmp/v54-$arm" "$BASE"; done

# Apply the verified semantic incumbent to both arms: Pi-only + relevance propagation-off.
for d in /tmp/v54-current /tmp/v54-rep; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY
done

cat >/tmp/v54-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v54-arena
cd /tmp/v54-arena
for t in init-prelude std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Current Arena-style PGO: train only on init-prelude.
mkdir -p /tmp/v54-current-pgo
(cd /tmp/v54-current && \
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v54-current-pgo" cargo build --release --locked)
/tmp/v54-current/target/release/sokonanoda /tmp/v54-config.json < /tmp/v54-arena/_build/tests/init-prelude.ndjson >/dev/null 2>/tmp/v54-current-train.err
llvm-profdata merge -o /tmp/v54-current-pgo/merged.profdata /tmp/v54-current-pgo
(cd /tmp/v54-current && \
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v54-current-pgo/merged.profdata" cargo build --release --locked)
cp /tmp/v54-current/target/release/sokonanoda /tmp/v54-current-bin

# Representative PGO: preserve init-prelude coverage, then add bounded deterministic
# prefixes from Std and Cedar. Full Std instrumentation segfaulted before profile merge;
# this is the smallest corpus-size distinction that failure forces. Mathlib stays held out.
mkdir -p /tmp/v54-rep-pgo
(cd /tmp/v54-rep && \
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v54-rep-pgo" cargo build --release --locked)
/tmp/v54-rep/target/release/sokonanoda /tmp/v54-config.json < /tmp/v54-arena/_build/tests/init-prelude.ndjson >/dev/null 2>/tmp/v54-rep-init-train.err
head -n 250000 /tmp/v54-arena/_build/tests/std.ndjson | /tmp/v54-rep/target/release/sokonanoda /tmp/v54-config.json >/dev/null 2>/tmp/v54-rep-std-train.err
head -n 250000 /tmp/v54-arena/_build/tests/cedar.ndjson | /tmp/v54-rep/target/release/sokonanoda /tmp/v54-config.json >/dev/null 2>/tmp/v54-rep-cedar-train.err
llvm-profdata merge -o /tmp/v54-rep-pgo/merged.profdata /tmp/v54-rep-pgo
(cd /tmp/v54-rep && \
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v54-rep-pgo/merged.profdata" cargo build --release --locked)
cp /tmp/v54-rep/target/release/sokonanoda /tmp/v54-rep-bin

# Semantic replay on held-out Mathlib must be exact.
/tmp/v54-current-bin /tmp/v54-config.json < /tmp/v54-arena/_build/tests/mathlib.ndjson >/tmp/v54-current.out 2>/tmp/v54-current.err
/tmp/v54-rep-bin /tmp/v54-config.json < /tmp/v54-arena/_build/tests/mathlib.ndjson >/tmp/v54-rep.out 2>/tmp/v54-rep.err
cmp /tmp/v54-current.out /tmp/v54-rep.out
echo V54_MATHLIB_SEMANTIC_REPLAY=EXACT

# Alternating held-out Mathlib wall-time tournament.
orders=("current rep" "rep current" "current rep")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v54-${arm}-${r}.time" \
      "/tmp/v54-$arm-bin" /tmp/v54-config.json < /tmp/v54-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v54-${arm}-${r}.err"
  done
done

python3 - <<'PY' | tee /tmp/v54-decision.txt
from pathlib import Path
from statistics import median
vals={}
for a in ('current','rep'):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v54-{a}-*.time'))]
    assert len(xs)==3,(a,xs)
    vals[a]=median(xs)
    print(f'V54_TIMES {a} raw={xs} median={vals[a]:.3f}')
d=(vals['rep']/vals['current']-1)*100
print(f'V54_REPRESENTATIVE_PGO_MATHLIB_DELTA={d:+.4f}%')
if d <= -2.0:
    print('DECISION=V54_REPRESENTATIVE_PGO_MATERIAL_TRANSFER_WIN__ADVANCE_CORPUS_FACTORIAL')
elif d < 0:
    print('DECISION=V54_REPRESENTATIVE_PGO_WEAK_WIN__RETAIN_ONLY_IF_FULL_ARENA_SCORE_TRANSFERS')
else:
    print('DECISION=V54_REPRESENTATIVE_PGO_KILL__INIT_PRELUDE_PROFILE_NOT_THE_LIMITER')
print('RULE=CHANGE_ONLY_THE_PROFILE_DISTINCTION_FORCED_BY_MEASURED_TRANSFER')
PY
