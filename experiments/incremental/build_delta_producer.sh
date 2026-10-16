#!/usr/bin/env bash
# Native build against the exact qualification toolchain and bundled exporter.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="${1:-${repo_root}/target/incremental-producer}"
mkdir -p "$build_dir"
if [[ -n "${LEAN_SYSROOT:-}" ]]; then
  lean_bin="${LEAN_SYSROOT}/bin/lean"
  leanc_bin="${LEAN_SYSROOT}/bin/leanc"
else
  elan_bin="${ELAN:-elan}"
  lean_prefix="$("$elan_bin" run leanprover/lean4:v4.35.0 lean --print-prefix)"
  lean_bin="${lean_prefix}/bin/lean"
  leanc_bin="$(dirname "$lean_bin")/leanc"
fi
export PATH="$(dirname "$lean_bin"):$PATH"
[[ "$("$lean_bin" --githash)" == eb6cafb7290e8bd5f2937522d8d804f58f02bafc ]] || {
  echo 'wrong Lean revision' >&2; exit 1;
}
"$lean_bin" -c "${build_dir}/DeltaProducer.c" "${repo_root}/experiments/incremental/DeltaProducer.lean"
"$leanc_bin" -o "${build_dir}/delta-producer" "${build_dir}/DeltaProducer.c" -lLeanExport -rdynamic
printf '%s\n' "${build_dir}/delta-producer"
