#!/usr/bin/env bash
set -euxo pipefail

# Reconstruct exact full-Arena-verified Pi+v18 incumbent and matched grind trace.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

rm -rf /tmp/v27-candidate /tmp/v27-target
cp -a /tmp/v21-compound /tmp/v27-candidate
python3 experiments/apply_one_cons_framed_prune_fastpath_v27.py /tmp/v27-candidate

(cd /tmp/v27-candidate && cargo test --release --locked)
(cd /tmp/v27-candidate && CARGO_TARGET_DIR=/tmp/v27-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
cp /tmp/v27-target/release/sokonanoda /tmp/v27-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v27-bin /tmp/v21-checker.json < "$F" >/tmp/v27.out 2>/tmp/v27.err
cmp /tmp/v21-compound.out /tmp/v27.out
echo V27_SEMANTIC_REPLAY=EXACT | tee /tmp/v27-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v27.cg /tmp/v27-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v27.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.10 /tmp/v27.cg > /tmp/v27-self.txt
'

python3 - <<'PY' | tee /tmp/v27-decision.txt
from pathlib import Path
import re

def total(path):
    txt=Path(path).read_text(errors='replace')
    m=re.search(r'^summary:\s*(\d+)', txt, re.M)
    if not m: raise SystemExit('NO_SUMMARY '+path)
    return int(m.group(1))
inc=total('/tmp/v21-compound.cg')
cand=total('/tmp/v27.cg')
d=(cand-inc)/inc*100.0
print('V27_SEMANTIC_REPLAY=EXACT')
print(f'INCUMBENT_IR={inc}')
print(f'V27_IR={cand}')
print(f'V27_VS_INCUMBENT_PCT={d:+.4f}')
text=Path('/tmp/v27-self.txt').read_text(errors='replace')
for line in text.splitlines():
    if 'prune_env_cold' in line:
        print('V27_PRUNE_SELF='+line.strip()); break
else: print('V27_PRUNE_SELF=NOT_IN_THRESHOLD_TABLE')
if d <= -2.0: decision='V27_MATERIAL_GAIN__ADVANCE_CEDAR'
elif d <= -0.25: decision='V27_POSITIVE__BROADEN_CEDAR_AND_STD'
elif d < 0: decision='V27_WEAK_POSITIVE__RETAIN_AND_COMPARE'
else: decision='V27_NO_GAIN__KILL_ONE_CONS_FRAMED_SPECIALIZATION'
print('DECISION='+decision)
PY
