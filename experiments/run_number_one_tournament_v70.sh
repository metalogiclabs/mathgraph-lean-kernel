#!/usr/bin/env bash
set -euo pipefail

BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v70
ARMS=(incumbent iota pidemand lookup4 lookup8 linear iota_pidemand iota_lookup8 iota_linear pidemand_lookup8 iota_pidemand_lookup8)
rm -rf "$ROOT" && mkdir -p "$ROOT"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout -q "$BASE"
for arm in "${ARMS[@]:1}"; do cp -a "$ROOT/incumbent" "$ROOT/$arm"; done

curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-iota-apply-fusion/scripts/apply_iota_apply_fusion.py -o "$ROOT/iota.py"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-infer-pi-demand-bypass/scripts/apply_infer_pi_bypass.py -o "$ROOT/pidemand.py"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-infer-pi-demand-bypass/scripts/apply_lookup_unroll.py -o "$ROOT/lookup.py"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/experiment/gold-sniff-transfer-v68/scripts/apply_linear_env_key.py -o "$ROOT/linear.py"

apply_iota(){ python3 "$ROOT/iota.py" "$1"; }
apply_pidemand(){ python3 "$ROOT/pidemand.py" "$1"; }
apply_lookup(){ python3 "$ROOT/lookup.py" "$1" "$2"; }
apply_linear(){ python3 "$ROOT/linear.py" "$1"; }

apply_iota "$ROOT/iota"
apply_pidemand "$ROOT/pidemand"
apply_lookup "$ROOT/lookup4" 4
apply_lookup "$ROOT/lookup8" 8
apply_linear "$ROOT/linear"
apply_iota "$ROOT/iota_pidemand"; apply_pidemand "$ROOT/iota_pidemand"
apply_iota "$ROOT/iota_lookup8"; apply_lookup "$ROOT/iota_lookup8" 8
apply_iota "$ROOT/iota_linear"; apply_linear "$ROOT/iota_linear"
apply_pidemand "$ROOT/pidemand_lookup8"; apply_lookup "$ROOT/pidemand_lookup8" 8
apply_iota "$ROOT/iota_pidemand_lookup8"; apply_pidemand "$ROOT/iota_pidemand_lookup8"; apply_lookup "$ROOT/iota_pidemand_lookup8" 8

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V70_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in init-prelude std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build_plain(){
  arm=$1
  cd "$ROOT/$arm"
  rm -rf target
  RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q
  cp target/release/sokonanoda "$ROOT/$arm.plain.bin"
}
for arm in "${ARMS[@]}"; do build_plain "$arm"; done

mkdir -p "$ROOT/out"
"$ROOT/incumbent.plain.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" > "$ROOT/out/incumbent.std.out"
echo 'arm,pass,seconds' > "$ROOT/smoke.csv"
for arm in "${ARMS[@]}"; do
  if [[ "$arm" != incumbent ]]; then
    "$ROOT/$arm.plain.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" > "$ROOT/out/$arm.std.out"
    cmp "$ROOT/out/incumbent.std.out" "$ROOT/out/$arm.std.out"
    echo "V70_${arm^^}_STD_REPLAY=EXACT"
  fi
  for pass in 1 2 3; do
    sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.plain.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" >/dev/null; cat "$ROOT/t")
    echo "$arm,$pass,$sec" >> "$ROOT/smoke.csv"
  done
done

python3 - <<'PY' | tee "$ROOT/smoke-summary.txt"
import csv,statistics
rows=list(csv.DictReader(open('/tmp/v70/smoke.csv')))
arms=sorted({r['arm'] for r in rows})
med={a:statistics.median(float(r['seconds']) for r in rows if r['arm']==a) for a in arms}
base=med['incumbent']
rank=[]
print(f'V70_SMOKE_INCUMBENT={base:.3f}')
for a in arms:
    if a=='incumbent': continue
    d=(med[a]/base-1)*100
    rank.append((d,a))
    print(f'V70_SMOKE_{a.upper()}={med[a]:.3f} DELTA={d:.4f}%')
rank.sort()
w=[a for _,a in rank[:4]]
print('V70_SMOKE_TOP4='+','.join(w))
open('/tmp/v70/top4','w').write('\n'.join(w)+'\n')
PY

mapfile -t TOP4 < "$ROOT/top4"
FINAL=(incumbent "${TOP4[@]}")

build_pgo(){
  arm=$1
  cd "$ROOT/$arm"
  rm -rf target pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked -q
  cp target/release/sokonanoda "$ROOT/$arm.pgo.bin"
}
for arm in "${FINAL[@]}"; do build_pgo "$arm"; done

echo 'corpus,arm,pass,seconds' > "$ROOT/final.csv"
for corpus in std cedar mathlib; do
  "$ROOT/incumbent.pgo.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/incumbent.$corpus.out"
  for arm in "${FINAL[@]}"; do
    if [[ "$arm" != incumbent ]]; then
      "$ROOT/$arm.pgo.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/$arm.$corpus.out"
      cmp "$ROOT/out/incumbent.$corpus.out" "$ROOT/out/$arm.$corpus.out"
      echo "V70_${arm^^}_${corpus^^}_REPLAY=EXACT"
    fi
    for pass in 1 2 3; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.pgo.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/final.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v70/final.csv')))
arms=sorted({r['arm'] for r in rows})
corpora=('std','cedar','mathlib')
med={(c,a):statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']==a) for c in corpora for a in arms}
print('TARGET=CLEAR_NUMBER_ONE_MARGIN')
print('LIVE_SOKO_SECONDS=131.5991')
print('LIVE_OLD_MATHGRAPH_SECONDS=136.5505')
rank=[]
for a in arms:
    if a=='incumbent': continue
    ds=[]
    for c in corpora:
        d=(med[(c,a)]/med[(c,'incumbent')]-1)*100
        ds.append(d)
        print(f'V70_{a.upper()}_{c.upper()}={med[(c,a)]:.3f} BASE={med[(c,"incumbent")]:.3f} DELTA={d:.4f}%')
    gm=(math.prod(1+d/100 for d in ds)**(1/len(ds))-1)*100
    worst=max(ds)
    rank.append((gm,worst,a,ds))
    print(f'V70_{a.upper()}_GEOMEAN_DELTA={gm:.4f}% WORST_CORPUS_DELTA={worst:.4f}%')
rank.sort()
best=rank[0]
print(f'V70_WINNER={best[2]}')
print(f'V70_WINNER_GEOMEAN_DELTA={best[0]:.4f}%')
print(f'V70_WINNER_WORST_CORPUS_DELTA={best[1]:.4f}%')
if best[0] <= -5.0 and best[1] <= -2.0:
    print('DECISION=V70_CLEAR_MARGIN_SIGNAL__RUN_OFFICIAL_ARENA_GATE')
elif best[0] <= -4.0 and best[1] <= 0.0:
    print('DECISION=V70_NUMBER_ONE_SIGNAL__RUN_OFFICIAL_ARENA_GATE')
else:
    print('DECISION=V70_INSUFFICIENT__DO_NOT_PROMOTE__READ_RESIDUAL_AND_CONTINUE')
PY
