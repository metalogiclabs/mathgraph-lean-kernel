#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 4 ]; then
  echo 'Usage: bash replay-evidence.sh /absolute/fresh-output /absolute/exact-source-rust /absolute/pinned-leanchecker /absolute/pinned-leanchecker-paranoid' >&2
  exit 2
fi
task_evidence_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
task_repo_dir=$(git -C "$task_evidence_dir" rev-parse --show-toplevel)
task_output_dir=$1
task_rust_binary=$2
task_cpp_binary=$3
task_paranoid_binary=$4
for task_path in "$task_output_dir" "$task_rust_binary" "$task_cpp_binary" "$task_paranoid_binary"; do
  [[ "$task_path" = /* ]] || { echo 'All arguments must be absolute paths.' >&2; exit 2; }
done
[ ! -e "$task_output_dir" ] || { echo 'Use a fresh output directory.' >&2; exit 2; }
cd "$task_evidence_dir"
sha256sum --check SHA256SUMS
mkdir -p -- "$task_output_dir"
python3 -B packaging/reconstruct_archive.py --manifest packaging/manifest.json --output "$task_output_dir/qualified.zip"
git -C "$task_repo_dir" worktree add --detach "$task_output_dir/qualified-source" d1b22447d23a928ae536cbe838a47fc9682a4b39
mkdir -- "$task_output_dir/review"
python3 -B independent-review/reviewer.py --artifact "$task_output_dir/qualified.zip" \
  --repo "$task_output_dir/qualified-source" --source d1b22447d23a928ae536cbe838a47fc9682a4b39 \
  --output "$task_output_dir/review/ci-review.json"
python3 -B independent-review/run_falsifiers.py --artifact "$task_output_dir/qualified.zip" \
  --repo "$task_output_dir/qualified-source" --source d1b22447d23a928ae536cbe838a47fc9682a4b39 \
  --output "$task_output_dir/review/falsifiers.json"
python3 -B independent-review/fresh_kernel_replay.py --artifact "$task_output_dir/qualified.zip" \
  --inputs "$task_output_dir/review/inputs.json" --repo "$task_output_dir/qualified-source" \
  --source d1b22447d23a928ae536cbe838a47fc9682a4b39 \
  --rust "$task_rust_binary" --cpp "$task_cpp_binary" --paranoid "$task_paranoid_binary" \
  --out "$task_output_dir/fresh-kernels"
python3 -B phases/analyze_phases.py --artifact "$task_output_dir/qualified.zip" \
  --expected-source d1b22447d23a928ae536cbe838a47fc9682a4b39 --ci-run 39679768047 \
  --out "$task_output_dir/phases"
echo 'Evidence review, directed falsifiers, exact-input fresh kernels and contextual phase arithmetic completed.'
