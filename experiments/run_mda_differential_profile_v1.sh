#!/usr/bin/env bash
set -euo pipefail

MG=d6a73279e6765e637f9741180cefbd7ef957d8e5
SK=28c03d0103e004610e4d47a4828965efb2b70af9
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-differential-profile-v1
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

echo "MDA_DIFF_MG=$MG"
echo "MDA_DIFF_SK=$SK"
echo "MDA_DIFF_ARENA=$ARENA"

sudo sysctl -w kernel.perf_event_paranoid=-1 || true

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test mathlib >/dev/null

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/mathgraph"
git -C "$ROOT/mathgraph" checkout -q "$MG"
git clone -q https://github.com/intgrah/sokonanoda "$ROOT/sokonanoda"
git -C "$ROOT/sokonanoda" checkout -q "$SK"

build_pgo () {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "MDA_DIFF_PGO_$tag=PASS"
}

build_pgo "$ROOT/mathgraph" MG
build_pgo "$ROOT/sokonanoda" SK

run_one () {
  local dir="$1"
  local tag="$2"
  local safe="$ROOT/out/$tag"
  mkdir -p "$safe"

  /usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$safe/time.txt"     "$dir/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/mathlib.ndjson" >/dev/null 2>"$safe/stderr.txt"

  set +e
  perf record -q -F 199 -e task-clock -o "$safe/perf.data" --     "$dir/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/mathlib.ndjson" >/dev/null 2>"$safe/perf-record.err"
  rc=$?
  set -e
  echo "MDA_DIFF_PROFILE_$tag rc=$rc $(cat "$safe/time.txt")"

  if [ "$rc" -eq 0 ]; then
    perf report --stdio --no-children --percent-limit 0.2 -i "$safe/perf.data"       > "$safe/perf-report.txt" 2>"$safe/perf-report.err" || true
  fi
}

run_one "$ROOT/mathgraph" mathgraph
run_one "$ROOT/sokonanoda" sokonanoda

python3 - "$ROOT" <<'PY'
import pathlib,re,json,sys
root=pathlib.Path(sys.argv[1])
def parse_time(p):
    s=p.read_text().strip()
    return {k:float(v) if k!="rss_kb" else int(v) for k,v in re.findall(r'(wall|user|sys|rss_kb)=([0-9.]+)',s)}
def parse_report(p):
    rows=[]
    if not p.exists(): return rows
    for line in p.read_text(errors="replace").splitlines():
        m=re.match(r'\s*([0-9.]+)%\s+.*?\s+([^\s].*)$', line)
        if m:
            pct=float(m.group(1)); sym=m.group(2).strip()
            rows.append({"pct":pct,"line":sym})
    return rows[:80]
data={
 "present":{"sha":"d6a73279e6765e637f9741180cefbd7ef957d8e5","time":parse_time(root/"out/mathgraph/time.txt"),"profile":parse_report(root/"out/mathgraph/perf-report.txt")},
 "comparator":{"sha":"28c03d0103e004610e4d47a4828965efb2b70af9","time":parse_time(root/"out/sokonanoda/time.txt"),"profile":parse_report(root/"out/sokonanoda/perf-report.txt")},
 "claim_boundary":"task-clock sampling localizes work only; it does not certify Arena instruction-count improvement"
}
(root/"evidence/differential-profile.json").write_text(json.dumps(data,indent=2)+"\n")
print("MDA_DIFF_COMPLETE=PASS")
PY

cp "$ROOT/out/mathgraph/time.txt" "$ROOT/evidence/mathgraph-time.txt"
cp "$ROOT/out/sokonanoda/time.txt" "$ROOT/evidence/sokonanoda-time.txt"
cp "$ROOT/out/mathgraph/perf-report.txt" "$ROOT/evidence/mathgraph-perf-report.txt" 2>/dev/null || true
cp "$ROOT/out/sokonanoda/perf-report.txt" "$ROOT/evidence/sokonanoda-perf-report.txt" 2>/dev/null || true
