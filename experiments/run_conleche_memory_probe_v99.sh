#!/usr/bin/env bash
set -euo pipefail
BASE=e4ba5230f2d13ea86d8bbf71df134b446456793c
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v99-memory
rm -rf "$ROOT" && mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/checker"
git -C "$ROOT/checker" checkout -q "$BASE"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cd "$ROOT/arena"
nix develop -c ./lka.py build-test con-leche >/dev/null
input=$(find "$ROOT/arena/_build/tests" -name con-leche.ndjson -print -quit)
test -n "$input"

cd "$ROOT/checker"
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q

for n in 1 2 3 4; do
  cat >"$ROOT/config-$n.json" <<EOF
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":$n,"print_success_message":false}
EOF
  echo "V99_MEMORY_THREADS=$n"
  set +e
  /usr/bin/time -v "$ROOT/checker/target/release/sokonanoda" "$ROOT/config-$n.json" < "$input" \
    >"$ROOT/out/t$n.out" 2>"$ROOT/out/t$n.err"
  rc=$?
  set -e
  echo "V99_MEMORY_T${n}_EXIT=$rc"
  rss=$(grep 'Maximum resident set size' "$ROOT/out/t$n.err" | tail -1 | awk '{print $6}' || true)
  elapsed=$(grep 'Elapsed (wall clock) time' "$ROOT/out/t$n.err" | tail -1 | sed 's/.*: //' || true)
  echo "V99_MEMORY_T${n}_MAX_RSS_KB=${rss:-unknown}"
  echo "V99_MEMORY_T${n}_ELAPSED=${elapsed:-unknown}"
done

python3 - "$ROOT" <<'PY'
import pathlib,re,json,sys
root=pathlib.Path(sys.argv[1]); out={}
for n in (1,2,3,4):
    txt=(root/'out'/f't{n}.err').read_text(errors='replace')
    m=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',txt)
    e=re.search(r'Elapsed \(wall clock\) time .*?:\s*([^\n]+)',txt)
    z=re.search(r'Command exited with non-zero status (\d+)',txt)
    out[str(n)]={'max_rss_kb':int(m.group(1)) if m else None,'elapsed':e.group(1).strip() if e else None,
                 'nonzero_status':int(z.group(1)) if z else 0}
(root/'memory.json').write_text(json.dumps(out,indent=2))
print('V99_MEMORY_PROBE_COMPLETE=PASS')
PY
