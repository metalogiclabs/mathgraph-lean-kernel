#!/usr/bin/env bash
set -euo pipefail

BASE=e4ba5230f2d13ea86d8bbf71df134b446456793c
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v99
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/checker"
git -C "$ROOT/checker" checkout -q "$BASE"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

echo "V99_BASE=$BASE"
echo "V99_ARENA=$ARENA"

cat >"$ROOT/checker/config.json" <<'EOF'
{
  "use_stdin": true,
  "nat_extension": true,
  "string_extension": true,
  "unpermitted_axiom_hard_error": false,
  "unsafe_permit_all_axioms": true,
  "num_threads": 4,
  "print_success_message": false
}
EOF

cd "$ROOT/arena"
tests=(
  con-leche
  perf/magma-list-pair-n7
  perf/magma-list-pair-n21
  perf/magma-list-deep-n21
  perf/magma-list-deep-n36
  perf/magma-string-n4
  perf/magma-string-pair-n9
)
for t in "${tests[@]}"; do
  echo "V99_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t"
done

cd "$ROOT/checker"
RUSTFLAGS='-C target-cpu=native' cargo test --release --locked -q
RUSTFLAGS='-C target-cpu=native' cargo test --locked -q
echo "V99_RUST_SUITES=PASS"

# Match the Arena submission build: train PGO on init-prelude.
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
cd "$ROOT/checker"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$ROOT/checker/pgo" cargo build --release --locked -q
"$ROOT/checker/target/release/sokonanoda" "$ROOT/checker/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
cd "$ROOT/arena"\nnix develop -c llvm-profdata merge -o "$ROOT/checker/pgo/merged.profdata" "$ROOT/checker/pgo"\ncd "$ROOT/checker"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$ROOT/checker/pgo/merged.profdata" cargo build --release --locked -q
echo "V99_PGO_BUILD=PASS"

# A diagnostic binary that bypasses main's outer catch_unwind, used only after a failure.
mkdir -p src/bin
cat > src/bin/v99_diag.rs <<'RS'
use sokonanoda::util::Config;
use std::path::Path;
use stumpalo::Arena;

fn main() {
    let p = std::env::args().nth(1).expect("config path");
    let arena = Arena::new();
    let cfg = Config::try_from(Path::new(&p)).expect("config");
    let (export_file, _) = cfg.to_export_file(arena.as_arena_ref()).expect("export");
    export_file.check_all_declars();
}
RS
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --bin v99_diag -q

python3 - "$ROOT" <<'PY'
import json, pathlib, subprocess, sys, time, os
root = pathlib.Path(sys.argv[1])
arena = root/'arena'
checker = root/'checker'
names = [
    'con-leche',
    'magma-list-pair-n7',
    'magma-list-pair-n21',
    'magma-list-deep-n21',
    'magma-list-deep-n36',
    'magma-string-n4',
    'magma-string-pair-n9',
]
results = {}
for name in names:
    matches = list((arena/'_build'/'tests').rglob(name + '.ndjson'))
    if len(matches) != 1:
        raise SystemExit(f'expected one built NDJSON for {name}, got {matches}')
    inp = matches[0]
    outp = root/'out'/f'{name}.out'
    errp = root/'out'/f'{name}.err'
    t0 = time.perf_counter()
    with inp.open('rb') as fin, outp.open('wb') as fout, errp.open('wb') as ferr:
        p = subprocess.run(
            [str(checker/'target/release/sokonanoda'), str(checker/'config.json')],
            stdin=fin, stdout=fout, stderr=ferr)
    dt = time.perf_counter()-t0
    results[name] = {
        'input': str(inp.relative_to(arena)),
        'exit_code': p.returncode,
        'wall_time': dt,
        'stdout_bytes': outp.stat().st_size,
        'stderr_bytes': errp.stat().st_size,
    }
    print(f"V99_{name.upper().replace('-','_')}_EXIT={p.returncode}")
    print(f"V99_{name.upper().replace('-','_')}_WALL={dt:.6f}")
(root/'frontier.json').write_text(json.dumps(results, indent=2))
PY

con_rc=$(python3 -c 'import json; print(json.load(open("/tmp/v99/frontier.json"))["con-leche"]["exit_code"])')
if [ "$con_rc" -ne 0 ]; then
  echo "V99_CON_LECHE_ACCEPT=FAIL"
  con_input=$(find "$ROOT/arena/_build/tests" -name con-leche.ndjson -print -quit)
  set +e
  RUST_BACKTRACE=1 "$ROOT/checker/target/release/v99_diag" "$ROOT/checker/config.json" < "$con_input"     >"$ROOT/out/con-leche-diagnostic.out" 2>"$ROOT/out/con-leche-diagnostic.err"
  diag_rc=$?
  set -e
  echo "V99_CON_LECHE_DIAGNOSTIC_EXIT=$diag_rc"
  echo "V99_CON_LECHE_DIAGNOSTIC_STDERR_BEGIN"
  tail -n 200 "$ROOT/out/con-leche-diagnostic.err" || true
  echo "V99_CON_LECHE_DIAGNOSTIC_STDERR_END"
  exit 1
fi

echo "V99_CON_LECHE_ACCEPT=PASS"
python3 - <<'PY'
import json
r=json.load(open('/tmp/v99/frontier.json'))
bad=[k for k,v in r.items() if v['exit_code'] != 0]
if bad:
    raise SystemExit('frontier acceptance failures: '+', '.join(bad))
print('V99_NEW_MAGMA_ACCEPTS=PASS')
print('V99_FRONTIER_COMPLETE=PASS')
PY
