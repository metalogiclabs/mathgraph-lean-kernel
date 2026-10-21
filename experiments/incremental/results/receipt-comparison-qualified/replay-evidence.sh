#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash replay-evidence.sh /absolute/path/to/fresh-review-output" >&2
  exit 2
fi
task_results_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
task_repo_dir=$(git -C "$task_results_dir" rev-parse --show-toplevel)
task_output_dir=$1
if [[ "$task_output_dir" != /* ]]; then
  echo "The output directory must be an absolute path." >&2
  exit 2
fi
if [ -e "$task_output_dir" ]; then
  echo "Use a fresh output directory; review extracts about 280 MB." >&2
  exit 2
fi

cd "$task_results_dir"
sha256sum --check SHA256SUMS
python3 -B independent-review/review_receipt_comparison.py \
  --repo "$task_repo_dir" --source 5dfe38b01ca7b1c67f70be4ffb2479978049239e \
  --run-id 39581949051 --job-id 119161428100 --artifact-id 12342450124 \
  --run ci/run-native.json --jobs ci/jobs-native.json --artifacts ci/artifacts-native.json \
  --archive ci-compact.zip --out "$task_output_dir" --falsifiers
python3 -B input-parity/compare_inputs.py \
  --ci-root "$task_output_dir/artifact" \
  --local-summary independent-kernels/summary.json \
  --out "$task_output_dir/independent-input-parity.json"
