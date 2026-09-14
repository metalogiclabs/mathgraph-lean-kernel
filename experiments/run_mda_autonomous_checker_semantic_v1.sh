#!/usr/bin/env bash
set -euo pipefail
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-auto-semantic-v1
CANDIDATE="$(git rev-parse HEAD)"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

echo "MDA_AUTO_SEMANTIC_CANDIDATE=$CANDIDATE"
cargo test --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"

python3 - "$CANDIDATE" <<'PY'
import pathlib,re,sys
p=pathlib.Path("checkers/mathgraph.yaml")
s=p.read_text(); sha=sys.argv[1]
s2,n=re.subn(r'(?m)^rev:\s*[0-9a-f]{40}\s*$',f"rev: {sha}",s,count=1)
if n!=1: raise SystemExit(f"REV_PATCH_COUNT={n}")
p.write_text(s2)
PY

nix develop -c ./lka.py build-checker mathgraph
echo "MDA_AUTO_SEMANTIC_BUILD_CHECKER=PASS"
nix develop -c ./lka.py build-test --skip-declined-by mathgraph
echo "MDA_AUTO_SEMANTIC_BUILD_TESTS=PASS"
rm -rf _results
nix develop -c ./lka.py run --checker mathgraph | tee "$ROOT/evidence/arena-run.log"

python3 - "$ROOT/arena/_results" "$ROOT/evidence/semantic.json" <<'PY'
import collections,json,pathlib,sys
resdir=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2])
rows=[json.loads(p.read_text()) for p in sorted(resdir.glob("mathgraph_*.json"))]
counts=collections.Counter(r.get("correctness","error") for r in rows)
bad=[r for r in rows if r.get("correctness") in ("incorrect","declined","error")]
payload={"schema":"mda-autonomous-checker-semantic-v1",
         "tests_run":len(rows),"correctness_counts":dict(counts),
         "bad":[{"test":r.get("test"),"correctness":r.get("correctness"),"status":r.get("status")} for r in bad],
         "pass":not bad}
out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
print("MDA_AUTO_SEMANTIC_RESULT="+json.dumps(payload,sort_keys=True))
if bad: raise SystemExit(1)
PY
echo "MDA_AUTO_SEMANTIC_VERDICT=FULL_PINNED_ARENA_PASS"
