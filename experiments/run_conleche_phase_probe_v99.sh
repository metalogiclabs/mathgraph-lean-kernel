#!/usr/bin/env bash
set -euo pipefail
BASE=e4ba5230f2d13ea86d8bbf71df134b446456793c
UPSTREAM=ceaabb593e830dd318bfefd1675be3142fad8eb7
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v99-phase
rm -rf "$ROOT" && mkdir -p "$ROOT/out"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test con-leche >/dev/null
input=$(find "$ROOT/arena/_build/tests" -name con-leche.ndjson -print -quit)
test -n "$input"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/current"
git -C "$ROOT/current" checkout -q "$BASE"
git clone -q https://github.com/intgrah/sokonanoda "$ROOT/upstream"
git -C "$ROOT/upstream" checkout -q "$UPSTREAM"

for arm in current upstream; do
  cd "$ROOT/$arm"
  RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q
done

cat >"$ROOT/parse.json" <<EOF
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false,"parse_only":true}
EOF
for n in 1 4; do
cat >"$ROOT/check-$n.json" <<EOF
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":$n,"print_success_message":false}
EOF
done

run_one() {
  arm="$1"; mode="$2"; cfg="$3"
  echo "V99_PHASE_BEGIN=$arm:$mode"
  set +e
  /usr/bin/time -v "$ROOT/$arm/target/release/sokonanoda" "$cfg" < "$input" \
    >"$ROOT/out/$arm-$mode.out" 2>"$ROOT/out/$arm-$mode.err"
  rc=$?
  set -e
  rss=$(grep 'Maximum resident set size' "$ROOT/out/$arm-$mode.err" | tail -1 | awk '{print $6}' || true)
  echo "V99_PHASE_${arm}_${mode}_EXIT=$rc"
  echo "V99_PHASE_${arm}_${mode}_MAX_RSS_KB=${rss:-unknown}"
}

run_one current parse "$ROOT/parse.json"
run_one current serial "$ROOT/check-1.json"
run_one upstream parse "$ROOT/parse.json"
run_one upstream serial "$ROOT/check-1.json"
run_one upstream four "$ROOT/check-4.json"

python3 - "$ROOT" <<'PY'
import json,pathlib,re,sys
root=pathlib.Path(sys.argv[1]); rows={}
for p in sorted((root/'out').glob('*.err')):
    txt=p.read_text(errors='replace')
    m=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',txt)
    z=re.search(r'Command exited with non-zero status (\d+)',txt)
    rows[p.stem]={'max_rss_kb':int(m.group(1)) if m else None,'exit':int(z.group(1)) if z else 0}
(root/'phase.json').write_text(json.dumps(rows,indent=2))
print('V99_PHASE_COMPLETE=PASS')
PY
