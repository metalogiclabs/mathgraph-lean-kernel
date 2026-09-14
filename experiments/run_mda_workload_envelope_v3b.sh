#!/usr/bin/env bash
set -euo pipefail

: "${MDA_MASK:?MDA_MASK required}"
: "${MDA_TEST_DIR:?MDA_TEST_DIR required}"

GENESIS_BASE=16ccc0ed1c28961e411452d1c1a608761d73929e
FULL=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT="/tmp/mda-workload-v3b-mask-${MDA_MASK}"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

COMMITS=(
  801cb6d918d0e383e4c6a3c6017ef945d42a0698
  2de1895a52d21ad266b77002defe3e6bc69bbcfd
  91ba5db4029290b257a08494559ec3283cddbee3
  eaf479a135c02e0daad6760eff9e049dd9f63576
  5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71
  d6a73279e6765e637f9741180cefbd7ef957d8e5
)

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/repo"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/full" "$FULL"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/genesis" "$GENESIS_BASE"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/solvent" "$FULL"

payload_hash () {
  local dir="$1"
  (
    cd "$dir"
    {
      printf 'Cargo.toml  '; sha256sum Cargo.toml | awk '{print $1}'
      printf 'Cargo.lock  '; sha256sum Cargo.lock | awk '{print $1}'
      find src tests -type f -print0 | sort -z | while IFS= read -r -d '' f; do
        printf '%s  ' "$f"
        sha256sum "$f" | awk '{print $1}'
      done
    } | sha256sum | awk '{print $1}'
  )
}

for bit in 0 1 2 3 4 5; do
  if (( MDA_MASK & (1 << bit) )); then
    git -C "$ROOT/genesis" cherry-pick --no-commit "${COMMITS[$bit]}"
  fi
done

for bit in 5 4 3 2 1 0; do
  if (( (MDA_MASK & (1 << bit)) == 0 )); then
    git -C "$ROOT/solvent" revert --no-commit "${COMMITS[$bit]}"
  fi
done

GHASH="$(payload_hash "$ROOT/genesis")"
SHASH="$(payload_hash "$ROOT/solvent")"
test "$GHASH" = "$SHASH"

semantic_replay () {
  local dir="$1"
  local out="$2"
  cargo test --manifest-path "$dir/Cargo.toml" --release --locked -q >"$out.cargo.out" 2>"$out.cargo.err"
  cargo build --manifest-path "$dir/Cargo.toml" --release --locked -q
  local bin="$dir/target/release/sokonanoda"
  run_case () {
    local test="$1"; local want="$2"
    set +e
    "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/$test.ndjson" >"$out.${test//\//_}.out" 2>"$out.${test//\//_}.err"
    local rc=$?
    set -e
    test "$rc" -eq "$want"
  }
  run_case init-prelude 0
  run_case extra-rec 1
  run_case rec-missing-ih 1
  run_case proj-of-stuck-prop 1
  run_case proj-of-subst-prop 1
}

semantic_replay "$ROOT/genesis" "$ROOT/out/genesis"
semantic_replay "$ROOT/solvent" "$ROOT/out/solvent"
cargo build --manifest-path "$ROOT/full/Cargo.toml" --release --locked -q

measure () {
  local label="$1"; local bin="$2"; local test="$3"; local timeout_s="$4"
  local safe="${test//\//_}"
  local tf="$ROOT/out/${label}-${safe}.time"
  local outf="$ROOT/out/${label}-${safe}.out"
  local errf="$ROOT/out/${label}-${safe}.err"
  set +e
  if [ "$timeout_s" = none ]; then
    /usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$tf"       "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/$test.ndjson" >"$outf" 2>"$errf"
    rc=$?
  else
    /usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$tf"       timeout --signal=TERM --kill-after=5 "${timeout_s}s"       "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/$test.ndjson" >"$outf" 2>"$errf"
    rc=$?
  fi
  set -e
  python3 - "$tf" "$label" "$test" "$rc" "$timeout_s" <<'PY'
import json,re,sys,pathlib
p,label,test,rc,timeout_s=sys.argv[1:]
txt=pathlib.Path(p).read_text(errors="replace") if pathlib.Path(p).exists() else ""
m=dict(re.findall(r'(wall|user|sys|rss_kb)=([0-9.]+)',txt))
row={
 "label":label,
 "test":test,
 "rc":int(rc),
 "timed_out":int(rc) in (124,137,143),
 "timeout_seconds":None if timeout_s=="none" else int(timeout_s),
 "wall":float(m["wall"]) if "wall" in m else None,
 "user":float(m["user"]) if "user" in m else None,
 "sys":float(m["sys"]) if "sys" in m else None,
 "rss_kb":int(float(m["rss_kb"])) if "rss_kb" in m else None,
}
row["cpu"]=None if row["user"] is None or row["sys"] is None else row["user"]+row["sys"]
print(json.dumps(row))
PY
}

FULL_BIN="$ROOT/full/target/release/sokonanoda"
CAND_BIN="$ROOT/genesis/target/release/sokonanoda"
: > "$ROOT/evidence/measurements.jsonl"

for test in mathlib con-leche; do
  frow="$(measure full "$FULL_BIN" "$test" none)"
  echo "$frow" | tee -a "$ROOT/evidence/measurements.jsonl"
  full_wall="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["wall"])' <<<"$frow")"
  budget="$(python3 - "$full_wall" <<'PY'
import math,sys
w=float(sys.argv[1])
print(max(45, math.ceil(2.5*w)))
PY
)"
  crow="$(measure candidate "$CAND_BIN" "$test" "$budget")"
  echo "$crow" | tee -a "$ROOT/evidence/measurements.jsonl"
done

python3 - "$ROOT" "$MDA_MASK" "$GHASH" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1]); mask=int(sys.argv[2]); source_hash=sys.argv[3]
rows=[json.loads(x) for x in (root/"evidence/measurements.jsonl").read_text().splitlines()]
by={(r["label"],r["test"]):r for r in rows}
details={}
sufficient=True
for t in ("mathlib","con-leche"):
    f=by[("full",t)]; c=by[("candidate",t)]
    wall_ratio=None if not f["wall"] or c["wall"] is None else c["wall"]/f["wall"]
    cpu_ratio=None if not f["cpu"] or c["cpu"] is None else c["cpu"]/f["cpu"]
    ok=(
      c["rc"]==0 and not c["timed_out"] and
      wall_ratio is not None and wall_ratio<=1.20 and
      cpu_ratio is not None and cpu_ratio<=1.20
    )
    if c["timed_out"]:
      # Controlled timeout is >2.5x full wall, so wall insufficiency is already proven.
      ok=False
    sufficient &= ok
    details[t]={
      "full":f,"candidate":c,
      "wall_ratio":wall_ratio,"cpu_ratio":cpu_ratio,
      "sufficient":ok
    }
out={
 "schema":"mda-workload-envelope-convergence-v3b",
 "mask":mask,
 "retained_count":mask.bit_count(),
 "source_payload_sha256":source_hash,
 "paired_source_identity":True,
 "semantic_replay":{"genesis":"PASS","solvent":"PASS"},
 "workloads":details,
 "workload_sufficient":bool(sufficient),
}
(root/"evidence/result.json").write_text(json.dumps(out,indent=2)+"\n")
print("MDA_V3B_MASK",mask,"sufficient="+str(bool(sufficient)))
for t,x in details.items():
    print("MDA_V3B",t,"wall_ratio="+str(x["wall_ratio"]),"cpu_ratio="+str(x["cpu_ratio"]),"timeout="+str(x["candidate"]["timed_out"]))
PY
