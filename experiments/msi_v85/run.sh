#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=${V85_ROOT:-/tmp/v85}
mkdir -p "$ROOT"
python3 -m unittest discover -s experiments/msi_v85 -p 'test_*.py'
if [[ ! -d "$ROOT/base/.git" ]]; then
  git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
fi
git -C "$ROOT/base" checkout -q --detach "$BASE"
if [[ ! -d "$ROOT/arena/.git" ]]; then
  git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
fi
git -C "$ROOT/arena" checkout -q --detach "$ARENA"
# Reuse one pinned Nix environment and one Cargo target for all cycles.
cd "$ROOT/arena"
exec nix develop -c python3 "$GITHUB_WORKSPACE/experiments/msi_v85/optimizer.py" --root "$ROOT/results" --source "$ROOT/base" --arena "$ROOT/arena"
