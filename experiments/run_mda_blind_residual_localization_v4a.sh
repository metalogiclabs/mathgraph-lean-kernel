#!/usr/bin/env bash
set -euo pipefail

: "${MDA_TEST_DIR:?MDA_TEST_DIR required}"

ROOT=/tmp/mda-v4a
GENESIS_BASE=16ccc0ed1c28961e411452d1c1a608761d73929e
FULL=d6a73279e6765e637f9741180cefbd7ef957d8e5
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
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/seed" "$GENESIS_BASE"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/frontier" "$GENESIS_BASE"

apply_mask () {
  local dir="$1"; local mask="$2"
  for bit in 0 1 2 3 4 5; do
    if (( mask & (1 << bit) )); then
      git -C "$dir" cherry-pick --no-commit "${COMMITS[$bit]}" >/dev/null
    fi
  done
}

apply_mask "$ROOT/seed" 2
apply_mask "$ROOT/frontier" 62

semantic_replay () {
  local dir="$1"; local label="$2"
  cargo test --manifest-path "$dir/Cargo.toml" --release --locked -q     >"$ROOT/out/$label-cargo.out" 2>"$ROOT/out/$label-cargo.err"
  cargo build --manifest-path "$dir/Cargo.toml" --release --locked -q
  local bin="$dir/target/release/sokonanoda"
  run_case () {
    local test="$1"; local want="$2"
    set +e
    "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/$test.ndjson"       >"$ROOT/out/$label-${test//\//_}.out"       2>"$ROOT/out/$label-${test//\//_}.err"
    local rc=$?
    set -e
    printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" >> "$ROOT/evidence/$label-semantic.tsv"
    test "$rc" -eq "$want"
  }
  : > "$ROOT/evidence/$label-semantic.tsv"
  run_case init-prelude 0
  run_case extra-rec 1
  run_case rec-missing-ih 1
  run_case proj-of-stuck-prop 1
  run_case proj-of-subst-prop 1
}

semantic_replay "$ROOT/seed" seed
semantic_replay "$ROOT/frontier" frontier

sudo sysctl -w kernel.perf_event_paranoid=-1 >/dev/null || true

profile_one () {
  local label="$1"; local dir="$2"; local limit="$3"
  local bin="$dir/target/release/sokonanoda"
  local data="$ROOT/out/$label.perf.data"
  local report="$ROOT/out/$label.perf-report.txt"
  set +e
  perf record -q -F 199 -e task-clock -o "$data" --     timeout --signal=TERM --kill-after=5 "${limit}s"     "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/con-leche.ndjson"     >"$ROOT/out/$label.profile.out" 2>"$ROOT/out/$label.profile.err"
  local rc=$?
  set -e
  perf report --stdio --no-children --percent-limit 0.0 -i "$data"     > "$report" 2> "$ROOT/out/$label.perf-report.err"
  echo "$label rc=$rc limit=$limit" | tee "$ROOT/evidence/$label-profile-status.txt"
}

profile_one seed "$ROOT/seed" 25
profile_one frontier "$ROOT/frontier" 60

python3 - "$ROOT" <<'PY'
import json,pathlib,re,sys
root=pathlib.Path(sys.argv[1])

def parse_report(path):
    rows=[]
    for line in path.read_text(errors="replace").splitlines():
        # perf --stdio commonly begins with: "  12.34%  comm  dso  [.] symbol"
        m=re.match(r'\s*([0-9]+(?:\.[0-9]+)?)%\s+(.+)$',line)
        if not m:
            continue
        pct=float(m.group(1))
        rest=m.group(2).strip()
        # Prefer text after "[.]" / "[k]" marker if present.
        sm=re.search(r'\[[^\]]\]\s+(.+)$',rest)
        sym=(sm.group(1) if sm else rest).strip()
        if sym and sym not in ("[unknown]","unknown"):
            rows.append((sym,pct,line))
    # perf can emit duplicate symbol rows due DSOs; aggregate by displayed symbol.
    out={}
    for sym,pct,line in rows:
        out[sym]=out.get(sym,0.0)+pct
    return out

seed=parse_report(root/"out/seed.perf-report.txt")
front=parse_report(root/"out/frontier.perf-report.txt")
syms=sorted(set(seed)|set(front))
ranked=[]
for s in syms:
    ps=seed.get(s,0.0); pf=front.get(s,0.0)
    residual=ps-pf
    ratio=None if pf==0 else ps/pf
    ranked.append({
        "symbol":s,
        "seed_pct":ps,
        "frontier_pct":pf,
        "residual_pp":residual,
        "seed_frontier_ratio":ratio,
        "seed_unique":ps>=0.5 and pf==0,
        "seed_at_least_2x":ps>=1.0 and (pf==0 or ps>=2*pf),
    })
ranked.sort(key=lambda r:(r["residual_pp"],r["seed_pct"]),reverse=True)
top5=sum(max(0,r["residual_pp"]) for r in ranked[:5])
top10=sum(max(0,r["residual_pp"]) for r in ranked[:10])
qualified=[r for r in ranked if r["seed_pct"]>=1.0 and r["residual_pp"]>=0.5]
data={
  "schema":"mda-blind-residual-localization-v4a",
  "seed_mask":2,
  "frontier_mask":62,
  "profile_windows_seconds":{"seed":25,"frontier":60},
  "qualified_residual_count":len(qualified),
  "top5_positive_residual_mass_pp":top5,
  "top10_positive_residual_mass_pp":top10,
  "top_residuals":ranked[:40],
  "seed_unique_over_0_5pct":[r for r in ranked if r["seed_unique"]][:40],
  "seed_at_least_2x_frontier":[r for r in ranked if r["seed_at_least_2x"]][:40],
  "verdict":"VERIFIED_BLIND_COMPUTATIONAL_RESIDUAL_LOCALIZATION" if qualified else "BLIND_RESIDUAL_NOT_LOCALIZED",
  "claim_boundary":"Task-clock symbol localization on con-leche only; correlation/localization, not causal repair proof."
}
(root/"evidence/evidence.json").write_text(json.dumps(data,indent=2)+"\n")
with (root/"evidence/summary.md").open("w") as f:
    f.write("# MDA Blind Residual Localization V4a\n\n")
    f.write(f'Verdict: **{data["verdict"]}**\n\n')
    f.write(f'Qualified residual symbols: {len(qualified)}.\n\n')
    f.write(f'Top-5 positive residual mass: {top5:.3f} pp.\n\n')
    f.write(f'Top-10 positive residual mass: {top10:.3f} pp.\n\n')
    f.write("## Top residual symbols\n\n")
    f.write("| # | symbol | seed % | frontier % | residual pp | ratio |\n|---:|---|---:|---:|---:|---:|\n")
    for i,r in enumerate(ranked[:20],1):
        ratio="inf" if r["frontier_pct"]==0 and r["seed_pct"]>0 else ("" if r["seed_frontier_ratio"] is None else f'{r["seed_frontier_ratio"]:.2f}')
        f.write(f'| {i} | `{r["symbol"].replace("|","/")}` | {r["seed_pct"]:.3f} | {r["frontier_pct"]:.3f} | {r["residual_pp"]:.3f} | {ratio} |\n')
print("MDA_V4A_VERDICT="+data["verdict"])
for r in ranked[:10]:
    print("MDA_V4A_RESIDUAL",json.dumps(r,sort_keys=True))
if not qualified:
    raise SystemExit(1)
PY
