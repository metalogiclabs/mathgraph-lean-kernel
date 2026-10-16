#!/usr/bin/env bash
# Pinned Linux x86_64 setup. The proof/export tools come from the Lean release.
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="$HOME/.cargo/bin:$HOME/.elan/bin:$PATH"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This qualification setup is pinned to Linux x86_64.' >&2
  exit 2
fi
if ! command -v elan >/dev/null 2>&1; then
  task_download="$(mktemp -d)"
  trap 'rm -rf "$task_download"' EXIT
  curl --fail --location --retry 3 \
    https://github.com/leanprover/elan/releases/download/v4.2.4/elan-x86_64-unknown-linux-gnu.tar.gz \
    --output "$task_download/elan.tar.gz"
  python3 - "$task_download/elan.tar.gz" "$task_root/experiments/incremental/pins.json" <<'PY'
import hashlib,json,sys
actual=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()
expected=json.load(open(sys.argv[2]))['elan_linux_x86_64_sha256']
assert actual==expected, 'elan release archive checksum mismatch'
PY
  tar -xzf "$task_download/elan.tar.gz" -C "$task_download"
  "$task_download/elan-init" -y --default-toolchain none --no-modify-path
fi
elan toolchain install leanprover/lean4:v4.35.0
lean_version="$(elan run leanprover/lean4:v4.35.0 lean --version)"
case "$lean_version" in
  *'version 4.35.0,'*'eb6cafb7290e8bd5f2937522d8d804f58f02bafc'*) ;;
  *) echo "Unexpected Lean provenance: $lean_version" >&2; exit 2 ;;
esac
rustup toolchain install 1.95.0 --profile minimal
cargo +1.95.0 build --release --locked --manifest-path "$task_root/Cargo.toml" --bins
elan run leanprover/lean4:v4.35.0 lean -DwarningAsError=true \
  "$task_root/experiments/incremental/BoundedReuse.lean"
