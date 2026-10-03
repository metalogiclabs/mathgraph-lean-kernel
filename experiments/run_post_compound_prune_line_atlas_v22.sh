#!/usr/bin/env bash
set -euxo pipefail

# Reuse the exact verified v21 compound construction and semantic gate.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

# The normal release build uses fat LTO, which preserves function symbols but can erase
# source attribution in Callgrind. Build a measurement-only copy of the SAME compound
# source with LTO disabled and full DWARF, then verify its output against the already
# replay-certified compound before profiling it.
rm -rf /tmp/v22-debug-target
(
  cd /tmp/v21-compound
  CARGO_TARGET_DIR=/tmp/v22-debug-target \
  CARGO_PROFILE_RELEASE_LTO=false \
  CARGO_PROFILE_RELEASE_DEBUG=2 \
  CARGO_PROFILE_RELEASE_STRIP=false \
  RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=2' \
    cargo build --release --locked
)
cp /tmp/v22-debug-target/release/sokonanoda /tmp/v22-debug-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v22-debug-bin /tmp/v21-checker.json < "$F" >/tmp/v22-debug.out 2>/tmp/v22-debug.err
cmp /tmp/v21-compound.out /tmp/v22-debug.out
echo V22_DEBUG_SEMANTIC_REPLAY=EXACT | tee /tmp/v22-debug-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v22-debug.cg \
  /tmp/v22-debug-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v22-debug.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.00 --auto=yes \
  /tmp/v22-debug.cg /tmp/v21-compound/src/eval.rs > /tmp/v22-line-annotate.txt
'

python3 - <<'PY' | tee /tmp/v22-decision.txt
from pathlib import Path
text=Path('/tmp/v22-line-annotate.txt').read_text(errors='replace')
print('MEASUREMENT=EXCLUSIVE_SELF_SOURCE_LINE_INSTRUCTIONS')
print('SEMANTIC_REPLAY=EXACT_FROM_V21_HARNESS')
print('DEBUG_BUILD_REPLAY=EXACT')

lines=text.splitlines()
need=('fn prune_env_cold', 'fn intern_frame')
found_all=True
for key in need:
    hits=[i for i,l in enumerate(lines) if key in l]
    print(f'BEGIN_{key.replace(" ","_").upper()}')
    if not hits:
        found_all=False
        print('NOT_FOUND_IN_ANNOTATION')
    else:
        i=hits[0]
        for l in lines[max(0,i-8):min(len(lines),i+95)]:
            print(l)
    print(f'END_{key.replace(" ","_").upper()}')

print('SOURCE_ATTRIBUTION=' + ('RESOLVED' if found_all else 'UNRESOLVED'))
print('DECISION=' + ('READ_DOMINANT_PRUNE_COLD_SOURCE_PHASE__THEN_CHALLENGE_ON_INCUMBENT' if found_all else 'INSTRUMENTATION_FAILURE__DO_NOT_INFER_PHASE'))
PY
