#!/usr/bin/env bash
set -euxo pipefail
cp experiments/run_relevance_ablation_v43.sh /tmp/v43-run.sh
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v43-run.sh')
s=p.read_text()
s=s.replace("pub(crate) fn sig_of(&mut self, _name: NamePtr<'t>, _levels: LevelsPtr<'t>) -> Sig", "pub(crate) fn sig_of(&mut self, name: NamePtr<'t>, levels: LevelsPtr<'t>) -> Sig")
p.write_text(s)
PY
bash /tmp/v43-run.sh
