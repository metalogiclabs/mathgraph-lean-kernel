#!/usr/bin/env bash
set -euxo pipefail

# Reconstruct the exact full-Arena-verified Pi+v18 incumbent and its grind trace.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

rm -rf /tmp/v24-candidate /tmp/v24-target
cp -a /tmp/v21-compound /tmp/v24-candidate
python3 experiments/apply_framed_two_slot_prune_v24.py /tmp/v24-candidate

(cd /tmp/v24-candidate && cargo test --release --locked)
(cd /tmp/v24-candidate && CARGO_TARGET_DIR=/tmp/v24-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
cp /tmp/v24-target/release/sokonanoda /tmp/v24-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v24-bin /tmp/v21-checker.json < "$F" >/tmp/v24.out 2>/tmp/v24.err
cmp /tmp/v21-compound.out /tmp/v24.out
echo V24_SEMANTIC_REPLAY=EXACT | tee /tmp/v24-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v24.cg /tmp/v24-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v24.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.10 /tmp/v24.cg > /tmp/v24-self.txt
'

python3 - <<'PY' | tee /tmp/v24-decision.txt
from pathlib import Path
import re

def total(path):
    txt=Path(path).read_text(errors='replace')
    m=re.search(r'^summary:\s*(\d+)', txt, re.M)
    if not m: raise SystemExit(f'NO_SUMMARY {path}')
    return int(m.group(1))
inc=total('/tmp/v21-compound.cg')
cand=total('/tmp/v24.cg')
delta=(cand-inc)/inc*100.0
print('V24_SEMANTIC_REPLAY=EXACT')
print(f'INCUMBENT_IR={inc}')
print(f'V24_IR={cand}')
print(f'V24_VS_INCUMBENT_PCT={delta:+.4f}')
text=Path('/tmp/v24-self.txt').read_text(errors='replace')
for line in text.splitlines():
    if 'prune_env_cold' in line:
        print('V24_PRUNE_SELF='+line.strip())
        break
else:
    print('V24_PRUNE_SELF=NOT_IN_THRESHOLD_TABLE')
if delta <= -5.0:
    decision='V24_BIG_GAIN__IMMEDIATE_FULL_GATE'
elif delta <= -2.0:
    decision='V24_MATERIAL_GAIN__ADVANCE_CEDAR'
elif delta <= -0.25:
    decision='V24_POSITIVE__BROADEN_CEDAR_AND_STD'
elif delta < 0:
    decision='V24_WEAK_POSITIVE__RETAIN_ONLY_AS_EVIDENCE'
else:
    decision='V24_NO_GAIN__KILL_TWO_SLOT_LOCALITY_HYPOTHESIS'
print('DECISION='+decision)
PY
