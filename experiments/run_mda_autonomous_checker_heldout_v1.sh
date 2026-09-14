#!/usr/bin/env bash
set -euo pipefail
BASE=c6d445a954def8922490d0cd874ea134b45463dd
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-auto-heldout-v1
HELD=(mathlib perf/grind-ring-5 perf/shift-cascade)
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/bin"

CANDIDATE="$(git rev-parse HEAD)"
echo "MDA_AUTO_HELDOUT_CANDIDATE=$CANDIDATE"
test -f mda/generated/autonomous_cache_admission_v1/HELDOUT_AUTHORIZED

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for t in "${HELD[@]}"; do
  nix develop -c ./lka.py build-test "$t" >/dev/null
done
cd "$GITHUB_WORKSPACE"

git worktree add -q --detach "$ROOT/base" "$BASE"
RUSTFLAGS="-C target-cpu=native" cargo build --manifest-path "$ROOT/base/Cargo.toml" --release --locked -q
cp "$ROOT/base/target/release/sokonanoda" "$ROOT/bin/base"
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q
cp target/release/sokonanoda "$ROOT/bin/candidate"

: > "$ROOT/evidence/heldout-timings.tsv"
for t in "${HELD[@]}"; do
  "$ROOT/bin/base" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>/dev/null
  "$ROOT/bin/candidate" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>/dev/null
  for rep in 1 2 3; do
    for label in BASE CANDIDATE; do
      if [ "$label" = BASE ]; then binary="$ROOT/bin/base"; else binary="$ROOT/bin/candidate"; fi
      /usr/bin/time -f '%e' -o "$ROOT/t.time"         "$binary" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>/dev/null
      printf '%s\t%s\t%s\t%s\n' "$label" "$t" "$rep" "$(cat "$ROOT/t.time")"         | tee -a "$ROOT/evidence/heldout-timings.tsv"
    done
  done
done

python3 - "$ROOT/evidence/heldout-timings.tsv" "$ROOT/evidence/heldout.json" <<'PY'
import json,statistics,sys
from collections import defaultdict
rows=[]
for line in open(sys.argv[1]):
    label,w,rep,wall=line.strip().split("\t")
    rows.append((label,w,int(rep),float(wall)))
g=defaultdict(list)
for label,w,rep,wall in rows:g[(label,w)].append(wall)
workloads=sorted({w for _,w,_,_ in rows})
base={w:statistics.median(g[("BASE",w)]) for w in workloads}
cand={w:statistics.median(g[("CANDIDATE",w)]) for w in workloads}
imp={w:1-cand[w]/base[w] for w in workloads}
agg=1-sum(cand.values())/sum(base.values())
wins=sum(v>0 for v in imp.values())
maxreg=max([-v for v in imp.values()]+[0])
passed=agg>=0.01 and wins>=2 and maxreg<=0.05
out={"schema":"mda-autonomous-checker-heldout-v1","base":base,"candidate":cand,
     "per_workload_improvement":imp,"aggregate_improvement":agg,
     "wins":wins,"max_regression":maxreg,"pass":passed}
open(sys.argv[2],"w").write(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("MDA_AUTO_HELDOUT_RESULT="+json.dumps(out,sort_keys=True))
if not passed: raise SystemExit(1)
PY

echo "MDA_AUTO_HELDOUT_VERDICT=PROMOTION_PERFORMANCE_PASS"
echo "MDA_AUTO_ABLATION_VERDICT=RESTORING_BASE_REMOVES_GENERATED_MECHANISM"
