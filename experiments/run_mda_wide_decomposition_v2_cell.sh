#!/usr/bin/env bash
set -euo pipefail

: "${MODE:?MODE required}"
BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT="/tmp/mda-wide-decomposition-v2-${MODE}"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

echo "MDA_WIDE_V2_MODE=$MODE"
echo "MDA_WIDE_V2_BASE=$BASE"
echo "MDA_WIDE_V2_ARENA=$ARENA"
grep -E 'MemTotal|SwapTotal' /proc/meminfo | tee "$ROOT/evidence/host-meminfo.txt"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for t in init-prelude extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop mathlib con-leche; do
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/repo"
git -C "$ROOT/repo" checkout -q "$BASE"

if [ "$MODE" = "acquire-only" ] || [ "$MODE" = "none" ]; then
  python3 - "$ROOT/repo/src/eval.rs" "$MODE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); mode=sys.argv[2]
s=p.read_text()
old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }
"""
if mode=="acquire-only":
    new="""        if k > 64 {
            let _ = self.exact_wide_uses(e);
            return env;
        }
"""
else:
    new="""        if k > 64 {
            return env;
        }
"""
assert s.count(old)==1, s.count(old)
p.write_text(s.replace(old,new))
PY
fi

cd "$ROOT/repo"
cargo test --release --locked -q
echo "MDA_WIDE_V2_TESTS=PASS"

rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$ROOT/repo/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$ROOT/repo/pgo/merged.profdata" "$ROOT/repo/pgo"
cd "$ROOT/repo"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$ROOT/repo/pgo/merged.profdata" cargo build --release --locked -q
echo "MDA_WIDE_V2_PGO=PASS"

: > "$ROOT/evidence/protected.tsv"
run_sem () {
  local test="$1" want="$2"
  set +e
  "$ROOT/repo/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$test.ndjson" >/dev/null 2>"$ROOT/out/${test//\//_}.err"
  local rc=$?
  set -e
  printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" | tee -a "$ROOT/evidence/protected.tsv"
  [ "$rc" -eq "$want" ]
}
for t in extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop; do run_sem "$t" 1; done
echo "MDA_WIDE_V2_PROTECTED=PASS"

# Repeat Mathlib twice to expose local timing noise.
: > "$ROOT/evidence/mathlib.tsv"
for rep in 1 2; do
  /usr/bin/time -f 'wall=%e\tuser=%U\tsys=%S\trss_kb=%M' -o "$ROOT/out/mathlib-$rep.time"     "$ROOT/repo/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/mathlib.ndjson" >/dev/null 2>"$ROOT/out/mathlib-$rep.err"
  printf 'rep=%s\t%s\n' "$rep" "$(cat "$ROOT/out/mathlib-$rep.time")" | tee -a "$ROOT/evidence/mathlib.tsv"
done
echo "MDA_WIDE_V2_MATHLIB=PASS"

# Explicit budgeted stress probe. This is measurement authority, not semantic ground.
python3 - "$ROOT" "$MODE" <<'PY'
import json,os,pathlib,signal,subprocess,sys,time
root=pathlib.Path(sys.argv[1]); mode=sys.argv[2]
cmd=[str(root/"repo/target/release/sokonanoda"),str(root/"config.json")]
inp=open(root/"arena/_build/tests/con-leche.ndjson","rb")
err=open(root/"out/con-leche.err","wb")
p=subprocess.Popen(cmd,stdin=inp,stdout=subprocess.DEVNULL,stderr=err)
t0=time.monotonic(); peak=0; classification=None
TIME_LIMIT=600.0
RSS_LIMIT_KB=12*1024*1024
while True:
    rc=p.poll()
    if rc is not None:
        classification="COMPLETED" if rc==0 else f"EXIT_{rc}"
        break
    dt=time.monotonic()-t0
    try:
        status=pathlib.Path(f"/proc/{p.pid}/status").read_text()
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                rss=int(line.split()[1]); peak=max(peak,rss)
                break
    except Exception:
        pass
    if peak>RSS_LIMIT_KB:
        classification="RSS_BUDGET"
        p.terminate()
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
        break
    if dt>TIME_LIMIT:
        classification="TIME_BUDGET"
        p.terminate()
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
        break
    time.sleep(0.25)
wall=time.monotonic()-t0
rc=p.returncode
out={"mode":mode,"classification":classification,"rc":rc,"wall":wall,"peak_rss_kb":peak,
     "time_limit_s":TIME_LIMIT,"rss_limit_kb":RSS_LIMIT_KB,
     "claim_boundary":"Budget classifications are stress/resource evidence, not semantic rejection."}
(root/"evidence/con-leche.json").write_text(json.dumps(out,indent=2)+"\n")
print("MDA_WIDE_V2_CONLECHE="+json.dumps(out,sort_keys=True))
PY

python3 - "$ROOT" "$MODE" <<'PY'
import json,pathlib,re,statistics,sys
root=pathlib.Path(sys.argv[1]); mode=sys.argv[2]
rows=[]
for line in (root/"evidence/mathlib.tsv").read_text().splitlines():
    row={}
    for x in line.split("\t"):
        k,v=x.split("=",1)
        row[k]=int(v) if k in ("rep","rss_kb") else float(v)
    rows.append(row)
summary={
 "schema":"mda-wide-decomposition-v2",
 "mode":mode,
 "mathlib":rows,
 "mathlib_wall_median":statistics.median(r["wall"] for r in rows),
 "mathlib_user_median":statistics.median(r["user"] for r in rows),
 "con_leche":json.loads((root/"evidence/con-leche.json").read_text()),
 "claim_boundary":"Local timing/resource evidence only; Arena instruction-count promotion remains unavailable locally."
}
(root/"evidence/summary.json").write_text(json.dumps(summary,indent=2)+"\n")
PY

echo "MDA_WIDE_V2_COMPLETE=PASS"
