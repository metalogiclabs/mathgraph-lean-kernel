#!/usr/bin/env bash
set -euo pipefail

CANDIDATE=c6d445a954def8922490d0cd874ea134b45463dd
BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-warm-candidate-promotion-v1
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

echo "MDA_PROMOTION_CANDIDATE=$CANDIDATE"
echo "MDA_PROMOTION_BASE=$BASE"
echo "MDA_PROMOTION_ARENA=$ARENA"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"

python3 - "$CANDIDATE" <<'PY'
import pathlib,sys,re
p=pathlib.Path("checkers/mathgraph.yaml")
s=p.read_text()
cand=sys.argv[1]
s2,n=re.subn(r'(?m)^rev:\s*[0-9a-f]{40}\s*$',f"rev: {cand}",s,count=1)
if n!=1: raise SystemExit(f"REV_PATCH_COUNT={n}")
p.write_text(s2)
PY

nix develop -c ./lka.py build-checker mathgraph
echo "MDA_PROMOTION_BUILD_CHECKER=PASS"

# Build the full pinned test set that this checker is expected to face.
nix develop -c ./lka.py build-test --skip-declined-by mathgraph
echo "MDA_PROMOTION_BUILD_TESTS=PASS"

rm -rf _results
nix develop -c ./lka.py run --checker mathgraph | tee "$ROOT/evidence/arena-run.log"

python3 - "$ROOT" <<'PY'
import json,pathlib,sys,collections
root=pathlib.Path(sys.argv[1])
resdir=root/"arena/_results"
rows=[]
for p in sorted(resdir.glob("mathgraph_*.json")):
    d=json.loads(p.read_text())
    rows.append(d)
counts=collections.Counter(d.get("correctness","error") for d in rows)
status=collections.Counter(d.get("status","error") for d in rows)
bad=[d for d in rows if d.get("correctness") in ("incorrect","declined","error")]
mathlib=next((d for d in rows if d.get("test")=="mathlib"),None)
summary={
 "candidate":"c6d445a954def8922490d0cd874ea134b45463dd",
 "arena":"ac1c13762de41b594fa24b90ede8cfd97ac6a765",
 "tests_run":len(rows),
 "correctness_counts":dict(counts),
 "status_counts":dict(status),
 "bad":[{"test":d.get("test"),"status":d.get("status"),"correctness":d.get("correctness"),"exit_code":d.get("exit_code")} for d in bad],
 "mathlib":mathlib,
 "claim_boundary":"Full pinned Arena correctness replay on GitHub-hosted runner. Hardware instruction authority unavailable locally; performance promotion remains UNKNOWN_AUTHORITY."
}
(root/"evidence/summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print("MDA_PROMOTION_TESTS_RUN="+str(len(rows)))
print("MDA_PROMOTION_COUNTS="+json.dumps(dict(counts),sort_keys=True))
print("MDA_PROMOTION_BAD="+str(len(bad)))
if mathlib:
    print("MDA_PROMOTION_MATHLIB="+json.dumps({k:mathlib.get(k) for k in ("status","correctness","wall_time","cpu_time","max_rss","instructions")},sort_keys=True))
if bad:
    raise SystemExit("ARENA_CORRECTNESS_REPLAY_FAILED")
print("MDA_PROMOTION_CORRECTNESS=PASS")
PY

# Causal ablation/control: compare candidate against the unchanged accepted present
# under the same build/test/PGO procedure on Mathlib + con-leche.
for rev in "$BASE" "$CANDIDATE"; do
  tag=$([ "$rev" = "$BASE" ] && echo base || echo candidate)
  dir="$ROOT/$tag"
  git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$dir"
  git -C "$dir" checkout -q "$rev"
  cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
  cd "$dir"
  cargo test --release --locked -q
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  for t in mathlib con-leche; do
    : > "$ROOT/evidence/${tag}-${t}.tsv"
    for rep in 1 2; do
      /usr/bin/time -f 'wall=%e\tuser=%U\tsys=%S\trss_kb=%M' -o "$ROOT/t.time"         "$dir/target/release/sokonanoda" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>"$ROOT/t.err"
      printf 'rep=%s\t%s\n' "$rep" "$(cat "$ROOT/t.time")" | tee -a "$ROOT/evidence/${tag}-${t}.tsv"
    done
  done
done

python3 - "$ROOT" <<'PY'
import json,pathlib,re,statistics,sys
root=pathlib.Path(sys.argv[1])
out={}
for tag in ("base","candidate"):
  out[tag]={}
  for test in ("mathlib","con-leche"):
    rows=[]
    for line in (root/f"evidence/{tag}-{test}.tsv").read_text().splitlines():
      row={}
      for x in line.split("\t"):
        k,v=x.split("=",1)
        row[k]=int(v) if k in ("rep","rss_kb") else float(v)
      rows.append(row)
    out[tag][test]={
      "rows":rows,
      "wall_median":statistics.median(r["wall"] for r in rows),
      "user_median":statistics.median(r["user"] for r in rows),
      "rss_median_kb":statistics.median(r["rss_kb"] for r in rows)
    }
out["claim_boundary"]="Causal local screening only. Arena ranking requires retired instructions from authoritative vPMU evaluator."
(root/"evidence/ablation.json").write_text(json.dumps(out,indent=2)+"\n")
print("MDA_PROMOTION_ABLATION="+json.dumps({
 "base_mathlib_wall":out["base"]["mathlib"]["wall_median"],
 "candidate_mathlib_wall":out["candidate"]["mathlib"]["wall_median"],
 "base_conleche_wall":out["base"]["con-leche"]["wall_median"],
 "candidate_conleche_wall":out["candidate"]["con-leche"]["wall_median"]
},sort_keys=True))
PY

echo "MDA_PROMOTION_COMPLETE=PASS"
