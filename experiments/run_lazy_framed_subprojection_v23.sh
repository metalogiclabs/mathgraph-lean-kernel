#!/usr/bin/env bash
set -euxo pipefail

# Reconstruct the exact verified Pi+v18 incumbent and its grind trace.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

rm -rf /tmp/v23-candidate /tmp/v23-target
cp -a /tmp/v21-compound /tmp/v23-candidate
python3 experiments/apply_lazy_framed_subprojection_v23.py /tmp/v23-candidate

# Candidate correctness/build gate.
(cd /tmp/v23-candidate && cargo test --release --locked)
(cd /tmp/v23-candidate && CARGO_TARGET_DIR=/tmp/v23-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
cp /tmp/v23-target/release/sokonanoda /tmp/v23-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v23-bin /tmp/v21-checker.json < "$F" >/tmp/v23.out 2>/tmp/v23.err
cmp /tmp/v21-compound.out /tmp/v23.out
echo V23_SEMANTIC_REPLAY=EXACT | tee /tmp/v23-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v23.cg /tmp/v23-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v23.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.10 /tmp/v23.cg > /tmp/v23-self.txt
'

python3 - <<'PY' | tee /tmp/v23-decision.txt
from pathlib import Path
import re

def total(path):
    txt=Path(path).read_text(errors='replace')
    m=re.search(r'^summary:\s*(\d+)', txt, re.M)
    if not m:
        raise SystemExit(f'NO_SUMMARY {path}')
    return int(m.group(1))

inc=total('/tmp/v21-compound.cg')
cand=total('/tmp/v23.cg')
delta=(cand-inc)/inc*100.0
print('V23_SEMANTIC_REPLAY=EXACT')
print(f'INCUMBENT_IR={inc}')
print(f'V23_IR={cand}')
print(f'V23_VS_INCUMBENT_PCT={delta:+.4f}')

text=Path('/tmp/v23-self.txt').read_text(errors='replace')
for line in text.splitlines():
    if 'prune_env_cold' in line:
        print('V23_PRUNE_SELF='+line.strip())
        break
else:
    print('V23_PRUNE_SELF=NOT_IN_THRESHOLD_TABLE')

if delta <= -5.0:
    decision='V23_BIG_GAIN__IMMEDIATE_FULL_GATE'
elif delta <= -2.0:
    decision='V23_MATERIAL_GAIN__ADVANCE_CEDAR'
elif delta < 0:
    decision='V23_SMALL_POSITIVE__BROADEN_BEFORE_RETENTION'
else:
    decision='V23_NO_GAIN__READ_RESIDUAL_AND_REPAIR_OR_KILL'
print('DECISION='+decision)
PY
