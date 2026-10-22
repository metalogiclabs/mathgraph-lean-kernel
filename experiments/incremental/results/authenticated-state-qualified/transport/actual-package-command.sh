#!/usr/bin/env bash
# READY ONLY: invoke only after root explicitly declares SPACE CLEAR.
set -euo pipefail
research_root=/workspace/kernel-audit/authenticated-state
ci_dir="$research_root/ci-cec9941"
packager="$research_root/evidence-packaging/package_provider_zip.py"
python3 - <<'PYCHECK'
from pathlib import Path
import hashlib,json
root=Path("/workspace/kernel-audit/authenticated-state")
helper=root/"evidence-packaging/package_provider_zip.py"
reader=root/"evidence-packaging/reconstruct_archive.py"
assert hashlib.sha256(helper.read_bytes()).hexdigest()=="97099965630a0694b7c0fe24f6bbf08eaad1b38bc6f443f4fbc19ac5c1706c64"
assert hashlib.sha256(reader.read_bytes()).hexdigest()=="d8fcf72c03c0e09e5d3c8634c9a0313905fcdbeabab9434fefd55e963236e1da"
run=json.loads((root/"ci-cec9941/downloads/run.json").read_bytes())
assert run["id"]==39709067518 and run["head_sha"]=="cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5"
assert run["status"]=="completed" and run["conclusion"]=="success"
PYCHECK
mkdir "$ci_dir/permanent-provider-parts"
python3 "$packager" \
  --input "$ci_dir/downloads/authenticated-state-compact-00-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip" \
  --expected-size 419430556 \
  --expected-sha256 f9c28e9f243344e3c6d897c52f62593b389b3e7121a0128b9ce565c3b38e277e \
  --source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 \
  --run-id 39709067518 \
  --artifact-id 12406026073 \
  --out "$ci_dir/permanent-provider-parts/compact-00" \
  > "$ci_dir/permanent-provider-parts/compact-00.log" 2>&1
python3 "$packager" \
  --input "$ci_dir/downloads/authenticated-state-compact-01-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip" \
  --expected-size 316730440 \
  --expected-sha256 a52bf07300b0a1bfb1799523c1b21727fb6fcd5eb4e7025877e3f3d3c3a973b9 \
  --source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 \
  --run-id 39709067518 \
  --artifact-id 12406205607 \
  --out "$ci_dir/permanent-provider-parts/compact-01" \
  > "$ci_dir/permanent-provider-parts/compact-01.log" 2>&1
