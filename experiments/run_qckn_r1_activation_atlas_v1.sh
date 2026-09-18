#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-r1-activation-atlas-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cat >"$ROOT/evidence/provenance.tsv" <<EOF
candidate_sha	$CANDIDATE_SHA
arena_sha	$ARENA_SHA
purpose	observational_r1_activation_context_atlas
selector_changed	false
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test perf/beta-ladder
nix develop -c ./lka.py build-test perf/grind-ring-5
nix develop -c ./lka.py build-test mathlib

cd "$GITHUB_WORKSPACE"
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --features qckn-r1-atlas
cp target/release/sokonanoda "$ROOT/candidate.bin"
sha256sum "$ROOT/candidate.bin" > "$ROOT/evidence/binary.sha256"

run_one() {
  local label="$1"
  local input="$ROOT/arena/_build/tests/$label.ndjson"
  local stem="${label//\//_}"
  set +e
  /usr/bin/time -f 'wall_s=%e\nmax_rss_kb=%M' -o "$ROOT/evidence/$stem.time" \
    "$ROOT/candidate.bin" "$ROOT/config.json" \
    < "$input" > "$ROOT/evidence/$stem.stdout" 2> "$ROOT/evidence/$stem.stderr"
  local rc=$?
  set -e
  echo "$rc" > "$ROOT/evidence/$stem.rc"
  test "$rc" -eq 0
  grep '^QCKN_R1_ATLAS' "$ROOT/evidence/$stem.stderr" > "$ROOT/evidence/$stem.atlas.tsv"
  test -s "$ROOT/evidence/$stem.atlas.tsv"
}

run_one perf/beta-ladder
run_one perf/grind-ring-5
run_one mathlib

python3 - "$ROOT/evidence" <<'PY' | tee "$ROOT/evidence/summary.txt"
from pathlib import Path
from collections import Counter
import sys, math, json

root=Path(sys.argv[1])
labels=("perf_beta-ladder","perf_grind-ring-5","mathlib")
band_names=("0-7","8-31","32-63","64+")

def decode(idx):
    check=idx//1024
    x=idx%1024
    bands=[]
    for power in (256,64,16,4,1):
        bands.append(x//power)
        x%=power
    return (check,*bands)

def load(label):
    c=Counter()
    for line in (root/f"{label}.atlas.tsv").read_text().splitlines():
        tag,idx,count=line.split("\t")
        assert tag=="QCKN_R1_ATLAS"
        c[int(idx)]+=int(count)
    return c

data={label:load(label) for label in labels}
for label,c in data.items():
    total=sum(c.values())
    assert total>0, f"no R1 activations for {label}"
    print(f"{label}\ttotal_activations={total}\tnonzero_buckets={len(c)}")
    for idx,count in c.most_common(20):
        check,depth,env,binder,arg,body=decode(idx)
        print(
            f"TOP\t{label}\tbucket={idx}\tcount={count}\tshare={count/total:.6f}"
            f"\tmode={'Check' if check else 'InferOnly'}"
            f"\tdepth={band_names[depth]}\tenv={band_names[env]}"
            f"\tbinder={band_names[binder]}\targ={band_names[arg]}\tbody={band_names[body]}"
        )

axes=("mode","depth","env","binder","arg","body")
for ai,axis in enumerate(axes):
    print(f"=== MARGINAL {axis} ===")
    for label,c in data.items():
        total=sum(c.values())
        m=Counter(decode(idx)[ai] for idx,count in c.items() for _ in [0])
        # Replace bucket-presence counts with activation-weighted counts.
        m=Counter()
        for idx,count in c.items():
            m[decode(idx)[ai]] += count
        parts=[]
        for k,v in sorted(m.items()):
            name=("InferOnly","Check")[k] if axis=="mode" else band_names[k]
            parts.append(f"{name}:{v/total:.6f}")
        print(f"{label}\t" + "\t".join(parts))

beta=data["perf_beta-ladder"]
grind=data["perf_grind-ring-5"]
mathlib=data["mathlib"]
beta_set=set(beta)
grind_set=set(grind)
math_total=sum(mathlib.values())
beta_overlap=sum(v for k,v in mathlib.items() if k in beta_set)
grind_overlap=sum(v for k,v in mathlib.items() if k in grind_set)
both_overlap=sum(v for k,v in mathlib.items() if k in beta_set and k in grind_set)
print(f"MATHLIB_IN_BETA_BUCKETS={beta_overlap}/{math_total}={beta_overlap/math_total:.6f}")
print(f"MATHLIB_IN_GRIND_BUCKETS={grind_overlap}/{math_total}={grind_overlap/math_total:.6f}")
print(f"MATHLIB_IN_BOTH_POSITIVE_BUCKETS={both_overlap}/{math_total}={both_overlap/math_total:.6f}")

# Rank simple one-axis predicates by beta retention and Mathlib exposure.
candidates=[]
for ai,axis in enumerate(axes):
    vals=range(2) if axis=="mode" else range(4)
    for value in vals:
        b=sum(n for idx,n in beta.items() if decode(idx)[ai]==value)/sum(beta.values())
        m=sum(n for idx,n in mathlib.items() if decode(idx)[ai]==value)/sum(mathlib.values())
        g=sum(n for idx,n in grind.items() if decode(idx)[ai]==value)/sum(grind.values())
        if b >= 0.90:
            score=b/(m+1e-12)
            name=("InferOnly","Check")[value] if axis=="mode" else band_names[value]
            candidates.append((score,b,g,m,axis,name))
print("=== SIMPLE_SEPARATOR_CANDIDATES beta_retention>=0.90 ===")
for score,b,g,m,axis,name in sorted(candidates, reverse=True)[:20]:
    print(f"{axis}={name}\tbeta={b:.6f}\tgrind={g:.6f}\tmathlib={m:.6f}\tenrichment={score:.3f}")

out={
    "totals":{k:sum(v.values()) for k,v in data.items()},
    "nonzero_buckets":{k:len(v) for k,v in data.items()},
    "mathlib_in_beta_buckets":beta_overlap/math_total,
    "mathlib_in_grind_buckets":grind_overlap/math_total,
    "mathlib_in_both_positive_buckets":both_overlap/math_total,
}
(root/"atlas-summary.json").write_text(json.dumps(out,indent=2))
print("DECISION=OBSERVATIONAL_ATLAS_ONLY__NO_SELECTOR_PROMOTED")
PY
