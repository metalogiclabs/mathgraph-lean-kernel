#!/usr/bin/env bash
set -euxo pipefail

# Reuse the exact verified v21 compound construction and semantic gate.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

# Re-read the same Callgrind trace at source-line granularity, exclusive/self cost only.
nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.00 --auto=yes \
  /tmp/v21-compound.cg /tmp/v21-compound/src/eval.rs > /tmp/v22-line-annotate.txt
'

python3 - <<'PY' | tee /tmp/v22-decision.txt
from pathlib import Path
text=Path('/tmp/v22-line-annotate.txt').read_text(errors='replace')
print('MEASUREMENT=EXCLUSIVE_SELF_SOURCE_LINE_INSTRUCTIONS')
print('SEMANTIC_REPLAY=EXACT_FROM_V21_HARNESS')

# Emit the auto-annotated source window containing prune_env_cold and intern_frame.
lines=text.splitlines()
need=('fn prune_env_cold', 'fn intern_frame')
for key in need:
    hits=[i for i,l in enumerate(lines) if key in l]
    print(f'BEGIN_{key.replace(" ","_").upper()}')
    if not hits:
        print('NOT_FOUND_IN_ANNOTATION')
    else:
        i=hits[0]
        for l in lines[max(0,i-8):min(len(lines),i+85)]:
            print(l)
    print(f'END_{key.replace(" ","_").upper()}')

print('DECISION=READ_DOMINANT_PRUNE_COLD_SOURCE_PHASE__THEN_CHALLENGE_ON_INCUMBENT')
PY
