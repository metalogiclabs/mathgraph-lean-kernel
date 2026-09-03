#!/usr/bin/env bash
set -euxo pipefail

# Reconstruct exact full-Arena-verified Pi+v18 incumbent + incumbent grind trace.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

rm -rf /tmp/v25-candidate /tmp/v25-target
cp -a /tmp/v21-compound /tmp/v25-candidate
python3 experiments/apply_sparse_open_eval_demand_key_v25.py /tmp/v25-candidate

(cd /tmp/v25-candidate && cargo test --release --locked)
(cd /tmp/v25-candidate && CARGO_TARGET_DIR=/tmp/v25-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
cp /tmp/v25-target/release/sokonanoda /tmp/v25-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v25-bin /tmp/v21-checker.json < "$F" >/tmp/v25.out 2>/tmp/v25.err
cmp /tmp/v21-compound.out /tmp/v25.out
echo V25_SEMANTIC_REPLAY=EXACT | tee /tmp/v25-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v25.cg /tmp/v25-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v25.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.10 /tmp/v25.cg > /tmp/v25-self.txt
'

python3 - <<'PY' | tee /tmp/v25-decision.txt
from pathlib import Path
import re

def total(path):
    txt=Path(path).read_text(errors='replace')
    m=re.search(r'^summary:\s*(\d+)', txt, re.M)
    if not m: raise SystemExit('NO_SUMMARY '+path)
    return int(m.group(1))
inc=total('/tmp/v21-compound.cg')
cand=total('/tmp/v25.cg')
d=(cand-inc)/inc*100.0
print('V25_SEMANTIC_REPLAY=EXACT')
print(f'INCUMBENT_IR={inc}')
print(f'V25_IR={cand}')
print(f'V25_VS_INCUMBENT_PCT={d:+.4f}')
text=Path('/tmp/v25-self.txt').read_text(errors='replace')
for line in text.splitlines():
    if 'prune_env_cold' in line:
        print('V25_PRUNE_SELF='+line.strip()); break
else: print('V25_PRUNE_SELF=NOT_IN_THRESHOLD_TABLE')
if d <= -5.0: decision='V25_BIG_GAIN__IMMEDIATE_FULL_GATE'
elif d <= -2.0: decision='V25_MATERIAL_GAIN__ADVANCE_CEDAR'
elif d < 0: decision='V25_SMALL_POSITIVE__BROADEN_SPARSE_KEY_CLASSES'
else: decision='V25_NO_GAIN__KILL_DIRECT_SPARSE_APP_KEY'
print('DECISION='+decision)
PY
