# Replay the exact qualification without agent state

Runtime source: `cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`.
Successful qualification: https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518.

The committed compact provider ZIPs are stored losslessly as 48 MiB XZ parts.
This preserves all 8,346 compact files, totaling 3,528,974,155 decoded bytes.
The six larger **full** provider parts are separately listed in `ci/artifacts.json`;
they were published by CI but were not downloaded or independently replayed here.
The local replay covers the complete compact package and new verification decisions.

Use a clone containing this evidence directory and the exact runtime commit. Set
`repo` to that clone. A fresh scratch directory needs room for the provider ZIPs,
3.53 GB decoded inputs, approximately 1 GB of fresh replay outputs, and toolchains.
All output paths below must be new. The readers refuse overwrite or source drift.

```sh
set -euo pipefail
repo=/absolute/path/to/mathgraph-lean-kernel
evidence="$repo/experiments/incremental/results/authenticated-state-qualified"
scratch="$(mktemp -d)"
mkdir "$scratch/provider"
cp "$evidence/provider/authenticated-state-index-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip" "$scratch/provider/"
python3 "$evidence/transport/reconstruct_archive.py" \
  --manifest "$evidence/provider/compact-00/manifest.json" \
  --output "$scratch/provider/authenticated-state-compact-00-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip"
python3 "$evidence/transport/reconstruct_archive.py" \
  --manifest "$evidence/provider/compact-01/manifest.json" \
  --output "$scratch/provider/authenticated-state-compact-01-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip"
python3 "$evidence/transport/reconstruct_packages.py" \
  --source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 --run-id 39709067518 \
  --run-metadata "$evidence/ci/run.json" \
  --artifacts-metadata "$evidence/ci/artifacts.json" \
  --index-zip "$scratch/provider/authenticated-state-index-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip" \
  --parts-dir "$scratch/provider" --out "$scratch/compact"
```

This checks provider ZIP sizes/SHA256/CRC, ordered inner pieces, the whole XZ
identity, safe exact tar coverage, and every persisted leaf. It gives no semantic
acceptance or historical HMAC authority by itself.

Create the pristine exact-source checkout and install/build its pinned tools.
`setup.sh` is the same pinned setup used by CI; installation requires network.
The standalone reader only needs `sokonanoda`, `export-index`, and the two pinned
Lean C++ binaries; independently rebuilding Rust avoids assuming identical
cross-host compiler output bytes.

```sh
git -C "$repo" worktree add --detach "$scratch/source" cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5
cd "$scratch/source"
export PATH="$HOME/.cargo/bin:$HOME/.elan/bin:$PATH"
bash experiments/incremental/setup.sh
cargo +1.95.0 build --release --locked --bin sokonanoda --bin export-index
lean_tools="$(dirname "$(elan run leanprover/lean4:v4.35.0 elan which lean)")"
python3 experiments/incremental/replay_authenticated_state.py \
  --benchmark "$scratch/compact/artifacts/authenticated-state" \
  --controls "$scratch/compact/artifacts/state-controls-original" \
  --controls "$scratch/compact/artifacts/state-controls-expanded" \
  --repo "$scratch/source" --source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 \
  --rust "$scratch/source/target/release/sokonanoda" \
  --indexer "$scratch/source/target/release/export-index" \
  --cpp "$lean_tools/leanchecker" --paranoid "$lean_tools/leanchecker-paranoid" \
  --out "$scratch/fresh-replay"
```

Do **not** pass `--allow-smoke`. Require `completed=true`, `passed=true`, 800
primary transitions, 7,242,720 declaration-witness comparisons, 100 controls,
and 108 fresh kernel processes in the resulting summary. These are repeated
witness comparisons, not 7.24 million unique declarations. The fresh processes
cover 80 positive changed exports with Rust, 16 representative positive C++/
paranoid runs, and 12 rejection runs. Every primary transition is tied to its
exact reconstructed/exported input and full-index witness.

The public reader imports no incremental engine or issuer. It reconstructs
complete exact bytes and fresh full indexes, compares all fingerprints and
checking partitions, and executes the actual kernels. It checks historical
content addresses and envelope domains but does **not** reauthenticate the
original secret HMACs. Actual-key authority, forged-delta and cold-recovery
controls executed inside the exact-source CI and are preserved in the package.
Regenerating the workflow uses a new issuer key and records its own actual Git
source; it is distinct from replaying this historical run.

Recompute the timing arithmetic independently:

```sh
python3 "$evidence/performance/frozen-helper/analyze_state.py" \
  --summary "$scratch/compact/artifacts/authenticated-state/summary.json" \
  --evidence-root "$scratch/compact" \
  --expected-source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 \
  --ci-run 39709067518 --out "$scratch/fresh-arithmetic"
```

This recomputes 28 recorded series and bootstrap intervals; it does not remeasure
CI timings or certify kernels. Warm figures are medians of five per-pair means
of ten edits. Full lifecycles include initialization, 40 changes and close.
Direct Rust input preparation is excluded, favoring that comparator. Cold
initialization is slower than a single fresh Rust check. No general break-even,
aggregate-memory saving, or asymptotic change-proportional claim follows.

`independent/` preserves this run's fresh replay summary, build/source pins,
execution record and lossless full-output archive. Its archival manifest records
how to reconstruct those historical outputs; fresh replay above remains the
independent acceptance test. `exploratory/` is a separate **local**, unqualified
negative probe: one changed leaf fingerprint still schedules 260 obligations on
the larger workload because the unchanged rule withdraws 259 later complex
obligations. It establishes no fixed-cone scaling speedup.
