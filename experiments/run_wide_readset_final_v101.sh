#!/usr/bin/env bash
set -euo pipefail
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v101-final
rm -rf "$ROOT" && mkdir -p "$ROOT/out" "$ROOT/tests"
echo "V101_FINAL_HEAD=$(git rev-parse HEAD)"
grep -E "MemTotal|SwapTotal" /proc/meminfo | sed "s/^/V101_FINAL_HOST_/"
cargo test --release --locked -q

curl -fsSL https://arena.lean-lang.org/results.json -o "$ROOT/results.json"
curl -fsSL https://arena.lean-lang.org/lean-arena-tests.tar.gz -o "$ROOT/tests.tar.gz"
sha256sum "$ROOT/results.json" "$ROOT/tests.tar.gz" | tee "$ROOT/input-sha256.txt"
python3 - "$ROOT/results.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); m=x.get("meta",{})
print("V101_FINAL_LIVE_ARENA_REV="+str(m.get("git_revision")))
print("V101_FINAL_LIVE_ARENA_RUN="+str(m.get("github_run_id")))
PY
tar -xzf "$ROOT/tests.tar.gz" -C "$ROOT/tests"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
cd "$GITHUB_WORKSPACE"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$GITHUB_WORKSPACE/pgo/merged.profdata" "$GITHUB_WORKSPACE/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked -q
echo "V101_FINAL_PGO_BUILD=PASS"

python3 - "$ROOT" "$GITHUB_WORKSPACE" <<'PY'
import pathlib,subprocess,json,sys,time
root=pathlib.Path(sys.argv[1]); ws=pathlib.Path(sys.argv[2])
bin=ws/"target/release/sokonanoda"; cfg=root/"config.json"
rows=[]; failures=[]
for expected,dirname,want in [("accept","good",0),("reject","bad",1)]:
  for p in sorted((root/"tests"/dirname).rglob("*.ndjson")):
    t=time.perf_counter()
    cp=subprocess.run(["timeout","300",str(bin),str(cfg)],stdin=p.open("rb"),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    dt=time.perf_counter()-t
    row={"test":str(p.relative_to(root/"tests"/dirname)),"expected":expected,"exit_code":cp.returncode,"wall_time":dt,"stderr":cp.stderr.decode(errors="replace")[-1000:]}
    rows.append(row)
    if cp.returncode != want:
      failures.append(row); print("V101_FINAL_SMALL_FAIL="+json.dumps(row),flush=True)
(root/"small-gate.json").write_text(json.dumps({"count":len(rows),"failures":failures,"rows":rows},indent=2))
print(f"V101_FINAL_SMALL_COUNT={len(rows)}")
print(f"V101_FINAL_SMALL_FAILURES={len(failures)}")
if failures: raise SystemExit(1)
print("V101_FINAL_SMALL_GATE=PASS")
PY

cd "$ROOT/arena"
for t in perf/magma-list-pair-n7 perf/magma-list-pair-n21 perf/magma-list-deep-n21 perf/magma-list-deep-n36 perf/magma-string-n4 perf/magma-string-pair-n9; do
  nix develop -c ./lka.py build-test "$t" >/dev/null
done
cd "$GITHUB_WORKSPACE"
fails=0
for t in perf/magma-list-pair-n7 perf/magma-list-pair-n21 perf/magma-list-deep-n21 perf/magma-list-deep-n36 perf/magma-string-n4 perf/magma-string-pair-n9; do
  f="$ROOT/arena/_build/tests/$t.ndjson"
  echo "V101_FINAL_SIX_BEGIN=$t"
  set +e; target/release/sokonanoda "$ROOT/config.json" < "$f" >/dev/null 2>"$ROOT/out/$(basename "$t").err"; rc=$?; set -e
  echo "V101_FINAL_SIX_EXIT_$t=$rc"
  [ "$rc" -eq 0 ] || fails=$((fails+1))
done
echo "V101_FINAL_SIX_FAILURES=$fails"
[ "$fails" -eq 0 ] || exit 1
echo "V101_FINAL_SIX_GATE=PASS"

cd "$ROOT/arena"
nix develop -c ./lka.py build-test con-leche >/dev/null
cd "$GITHUB_WORKSPACE"
echo "V101_FINAL_CONLECHE_BEGIN"
/usr/bin/time -v target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/con-leche.ndjson" >"$ROOT/out/conleche.out" 2>"$ROOT/out/conleche.err"
grep "Maximum resident set size" "$ROOT/out/conleche.err" | sed "s/^/V101_FINAL_CONLECHE_/"
grep "Elapsed (wall clock) time" "$ROOT/out/conleche.err" | sed "s/^/V101_FINAL_CONLECHE_/"
echo "V101_FINAL_CONLECHE=PASS"
echo "V101_FINAL_COMPLETE=PASS"
