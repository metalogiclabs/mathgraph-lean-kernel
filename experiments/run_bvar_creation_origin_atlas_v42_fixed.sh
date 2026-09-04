#!/usr/bin/env bash
set -euxo pipefail
python3 - <<'PY'
from pathlib import Path
p=Path('experiments/run_bvar_creation_origin_atlas_v42.sh')
s=p.read_text()
old="HashMap<(\\'static str, u32), (u64,u64,u64)>"
new="HashMap<(&'static str, u32), (u64,u64,u64)>"
assert old in s
p.write_text(s.replace(old,new,1))
PY
bash experiments/run_bvar_creation_origin_atlas_v42.sh
