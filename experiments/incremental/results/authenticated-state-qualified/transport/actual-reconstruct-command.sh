#!/usr/bin/env bash
# Run only after exact-source successful run metadata and all compact ZIPs exist.
set -euo pipefail
research_root=/workspace/kernel-audit/authenticated-state
ci_dir="$research_root/ci-cec9941"
python3 "$research_root/artifact-transport/reconstruct_packages.py"   --source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5   --run-id 39709067518   --run-metadata "$ci_dir/downloads/run.json"   --artifacts-metadata "$ci_dir/downloads/artifacts.json"   --index-zip "$ci_dir/downloads/authenticated-state-index-cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5.zip"   --parts-dir "$ci_dir/downloads"   --out "$ci_dir/extracted-compact"
