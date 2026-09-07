#!/usr/bin/env bash
set -euo pipefail
# The generated helper returns V<'t>, not the reference held by OnceCell::get.
# Keep the frozen tournament script intact and apply this source-generation fix.
ROOT=/tmp/v82-launch
mkdir -p "$ROOT"
python3 - "$ROOT/run.sh" <<'PY'
from pathlib import Path
import sys
s=Path('experiments/run_msi_cached_pi_v82.sh').read_text()
old="helper+='                    return cached;\\n'"
new="helper+='                    return *cached;\\n'"
assert s.count(old)==1, 'expected cached-return generator not found'
s=s.replace(old,new,1)
Path(sys.argv[1]).write_text(s)
PY
bash "$ROOT/run.sh"
