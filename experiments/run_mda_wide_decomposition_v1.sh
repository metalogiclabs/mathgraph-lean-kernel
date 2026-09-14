#!/usr/bin/env bash
set -euo pipefail

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-wide-decomposition-v1
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cd "$ROOT/arena"
for t in init-prelude extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop mathlib con-leche; do
  echo "MDA_WIDE_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

make_arm () {
  local mode="$1"
  local dir="$ROOT/$mode"
  git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$dir"
  git -C "$dir" checkout -q "$BASE"

  if [ "$mode" = "acquire-only" ] || [ "$mode" = "none" ]; then
    python3 - "$dir/src/eval.rs" "$mode" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); mode=sys.argv[2]
s=p.read_text()
old='''        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }
'''
if mode=="acquire-only":
    new='''        if k > 64 {
            let _ = self.exact_wide_uses(e);
            return env;
        }
'''
else:
    new='''        if k > 64 {
            return env;
        }
'''
if s.count(old)!=1:
    raise SystemExit(f"PATCH_ANCHOR_COUNT={s.count(old)}")
p.write_text(s.replace(old,new))
PY
  fi

  cd "$dir"
  cargo test --release --locked -q
  echo "MDA_WIDE_TESTS mode=$mode PASS"

  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "MDA_WIDE_PGO mode=$mode PASS"
}

for mode in full acquire-only none; do
  make_arm "$mode"
done

: > "$ROOT/evidence/results.tsv"

run_case () {
  local mode="$1"
  local test="$2"
  local want="$3"
  local timeout_s="$4"
  local tag="${mode}__${test//\//_}"
  local tf="$ROOT/out/$tag.time"
  set +e
  timeout "$timeout_s" /usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$tf"     "$ROOT/$mode/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$test.ndjson" >/dev/null 2>"$ROOT/out/$tag.err"
  local rc=$?
  set -e
  local metrics=""
  [ -s "$tf" ] && metrics="$(cat "$tf")"
  printf '%s\t%s\twant=%s\trc=%s\t%s\n' "$mode" "$test" "$want" "$rc" "$metrics" | tee -a "$ROOT/evidence/results.tsv"
  if [ "$rc" -ne "$want" ]; then
    echo "MDA_WIDE_CASE_FAIL mode=$mode test=$test want=$want rc=$rc"
    return 1
  fi
}

# Protected semantic replay first for every arm.
for mode in full acquire-only none; do
  for t in extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop; do
    run_case "$mode" "$t" 1 120
  done
  run_case "$mode" mathlib 0 600
done

# Full future-cost/stress observation. Timeout is experimental budget, not semantic recoding.
for mode in full acquire-only none; do
  set +e
  run_case "$mode" con-leche 0 900
  c_rc=$?
  set -e
  echo "MDA_WIDE_CONLECHE_CLASS mode=$mode result=$([ "$c_rc" -eq 0 ] && echo COMPLETED || echo BUDGET_OR_SEMANTIC_FAILURE)"
done

# Re-run unchanged full control at end to expose runner drift.
run_case full mathlib 0 600
run_case full con-leche 0 900

python3 - "$ROOT" <<'PY'
import json,pathlib,re,sys
root=pathlib.Path(sys.argv[1])
rows=[]
for line in (root/"evidence/results.tsv").read_text().splitlines():
    p=line.split("\t")
    row={"mode":p[0],"test":p[1],"want":int(p[2].split("=")[1]),"rc":int(p[3].split("=")[1])}
    for x in p[4:]:
        if "=" in x:
            k,v=x.split("=",1)
            try: row[k]=int(v) if k=="rss_kb" else float(v)
            except: row[k]=v
    rows.append(row)
data={
  "schema":"mda-wide-causal-decomposition-v1",
  "base":"d6a73279e6765e637f9741180cefbd7ef957d8e5",
  "arena":"ac1c13762de41b594fa24b90ede8cfd97ac6a765",
  "arms":{
    "full":"current wide mechanism",
    "acquire-only":"compute/cache exact wide read set but do not project environment",
    "none":"skip exact wide acquisition and projection for k>64"
  },
  "rows":rows,
  "claim_boundary":"Hosted wall/user/RSS are causal screening measurements only; Arena promotion still requires instruction-count authority."
}
(root/"evidence/summary.json").write_text(json.dumps(data,indent=2)+"\n")
PY

echo "MDA_WIDE_DECOMPOSITION_COMPLETE=PASS"
