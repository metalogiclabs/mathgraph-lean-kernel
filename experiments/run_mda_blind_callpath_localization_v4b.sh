#!/usr/bin/env bash
set -euo pipefail

: "${MDA_TEST_DIR:?MDA_TEST_DIR required}"

ROOT=/tmp/mda-v4b
GENESIS_BASE=16ccc0ed1c28961e411452d1c1a608761d73929e
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

build_one () {
  local dir="$1"
  RUSTFLAGS="-C force-frame-pointers=yes" cargo build --manifest-path "$dir/Cargo.toml" --release --locked -q
}
build_one "$ROOT/seed"
build_one "$ROOT/frontier"

sudo sysctl -w kernel.perf_event_paranoid=-1 >/dev/null || true

profile () {
  local label="$1"; local dir="$2"; local limit="$3"
  local bin="$dir/target/release/sokonanoda"
  local data="$ROOT/out/$label.perf.data"
  set +e
  perf record -q -F 99 -e task-clock -g --call-graph fp -o "$data" --     timeout --signal=TERM --kill-after=5 "${limit}s"     "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/con-leche.ndjson"     >"$ROOT/out/$label.out" 2>"$ROOT/out/$label.err"
  local rc=$?
  set -e
  perf script -i "$data" > "$ROOT/out/$label.script.txt" 2>"$ROOT/out/$label.script.err"
  echo "$label rc=$rc" > "$ROOT/evidence/$label-status.txt"
}

profile seed "$ROOT/seed" 20
profile frontier "$ROOT/frontier" 60

python3 - "$ROOT" <<'PY'
import collections,json,pathlib,re,sys
root=pathlib.Path(sys.argv[1])
TARGET="eval_no_cache"

def parse_blocks(path):
    text=path.read_text(errors="replace")
    blocks=[b for b in re.split(r'\n\s*\n',text) if b.strip()]
    stacks=[]
    for b in blocks:
        syms=[]
        for line in b.splitlines()[1:]:
            # Typical perf script frame:
            #     7f... symbol+0x... (dso)
            m=re.match(r'\s*[0-9a-fA-F]+\s+(.+?)(?:\+0x[0-9a-fA-F]+)?\s+\([^)]*\)\s*$',line)
            if m:
                syms.append(m.group(1).strip())
        if syms:
            stacks.append(syms)
    return stacks

def target_stats(stacks):
    callers=collections.Counter()
    paths=collections.Counter()
    target_samples=0
    examples=[]
    for st in stacks:
        idx=None
        for i,s in enumerate(st):
            if TARGET in s:
                idx=i
                break
        if idx is None:
            continue
        target_samples+=1
        caller=st[idx+1] if idx+1<len(st) else "<root>"
        callers[caller]+=1
        path=tuple(st[idx:min(len(st),idx+3)])
        paths[path]+=1
        if len(examples)<10:
            examples.append(st[:12])
    return target_samples,callers,paths,examples

data={}
for label in ("seed","frontier"):
    stacks=parse_blocks(root/f"out/{label}.script.txt")
    n,c,p,e=target_stats(stacks)
    data[label]={"samples":len(stacks),"target_samples":n,"callers":c,"paths":p,"examples":e}

def compare_counter(kind):
    out=[]
    cs=data["seed"][kind]; cf=data["frontier"][kind]
    ns=max(1,data["seed"]["target_samples"]); nf=max(1,data["frontier"]["target_samples"])
    keys=set(cs)|set(cf)
    for k in keys:
        ss=cs[k]/ns; sf=cf[k]/nf
        ratio=None if sf==0 else ss/sf
        out.append({
          "key":" -> ".join(k) if isinstance(k,tuple) else k,
          "seed_count":cs[k],"frontier_count":cf[k],
          "seed_share":ss,"frontier_share":sf,
          "residual_share":ss-sf,
          "ratio":ratio,
          "qualified":ss>=0.05 and (sf==0 or ss>=1.5*sf)
        })
    out.sort(key=lambda x:(x["residual_share"],x["seed_share"]),reverse=True)
    return out

callers=compare_counter("callers")
paths=compare_counter("paths")
qualified=[x for x in callers+paths if x["qualified"]]
verdict=(
 "VERIFIED_BLIND_CALLPATH_RESIDUAL_LOCALIZATION"
 if data["seed"]["target_samples"]>=50 and qualified
 else "BLIND_CALLPATH_RESIDUAL_NOT_LOCALIZED"
)
out={
 "schema":"mda-blind-callpath-localization-v4b",
 "target":TARGET,
 "seed_total_samples":data["seed"]["samples"],
 "frontier_total_samples":data["frontier"]["samples"],
 "seed_target_samples":data["seed"]["target_samples"],
 "frontier_target_samples":data["frontier"]["target_samples"],
 "caller_residuals":callers[:50],
 "path_residuals":paths[:50],
 "qualified_count":len(qualified),
 "seed_stack_examples":data["seed"]["examples"],
 "frontier_stack_examples":data["frontier"]["examples"],
 "verdict":verdict,
 "claim_boundary":"Sampled caller/path localization only; not causal proof of a repair."
}
(root/"evidence/evidence.json").write_text(json.dumps(out,indent=2)+"\n")
with (root/"evidence/summary.md").open("w") as f:
    f.write("# MDA Blind Call-Path Localization V4b\n\n")
    f.write(f"Verdict: **{verdict}**\n\n")
    f.write(f"SEED target samples: {data['seed']['target_samples']}; FRONTIER: {data['frontier']['target_samples']}.\n\n")
    f.write("## Caller residuals\n\n")
    f.write("| caller | seed share | frontier share | residual | ratio | qualified |\n|---|---:|---:|---:|---:|---|\n")
    for r in callers[:20]:
        rat="inf" if r["frontier_share"]==0 and r["seed_share"]>0 else ("" if r["ratio"] is None else f'{r["ratio"]:.2f}')
        f.write(f"| `{r['key'].replace('|','/')}` | {r['seed_share']:.3f} | {r['frontier_share']:.3f} | {r['residual_share']:.3f} | {rat} | {r['qualified']} |\n")
    f.write("\n## Three-frame path residuals\n\n")
    f.write("| path | seed share | frontier share | residual | ratio | qualified |\n|---|---:|---:|---:|---:|---|\n")
    for r in paths[:20]:
        rat="inf" if r["frontier_share"]==0 and r["seed_share"]>0 else ("" if r["ratio"] is None else f'{r["ratio"]:.2f}')
        f.write(f"| `{r['key'].replace('|','/')}` | {r['seed_share']:.3f} | {r['frontier_share']:.3f} | {r['residual_share']:.3f} | {rat} | {r['qualified']} |\n")
print("MDA_V4B_VERDICT="+verdict)
print("MDA_V4B_TARGET_SAMPLES seed="+str(data["seed"]["target_samples"])+" frontier="+str(data["frontier"]["target_samples"]))
for r in callers[:10]:
    print("MDA_V4B_CALLER",json.dumps(r,sort_keys=True))
for r in paths[:10]:
    print("MDA_V4B_PATH",json.dumps(r,sort_keys=True))
if verdict != "VERIFIED_BLIND_CALLPATH_RESIDUAL_LOCALIZATION":
    raise SystemExit(1)
PY
