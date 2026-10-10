#!/usr/bin/env bash
# Experimental, explicitly attributed sequential composition:
# pinned official sokonanoda is authoritative on decisive verdicts.
# Declined/internal outcomes are checked afresh by pinned MathGraph Flash.
# No test-name special-casing, no unverified theorem bypass.
set -uo pipefail
input="${1:?pass the exact lean4export NDJSON path}"
soko="${SOKO_BIN:-/tmp/msi-leader.bin}"
flash="${FLASH_BIN:-/tmp/msi-before.bin}"
flash_config="${FLASH_CONFIG:-/tmp/flash-msi-config1.json}"
"$soko" --stdin --nat-extension --string-extension \
  --axiom-allow-all --threads 1 < "$input"
verdict=$?
case "$verdict" in
  0|1)
    exit "$verdict"
    ;;
  2|3)
    if [[ "${ARENA_SERIAL_ROUTER_TRACE:-0}" == "1" ]]; then
      echo "MATHGRAPH_ROUTER:source=sokonanoda:result=$verdict:fallback=flash" >&2
    fi
    "$flash" "$flash_config" < "$input"
    exit $?
    ;;
  *)
    echo "MATHGRAPH_ROUTER:unexpected-primary-status=$verdict" >&2
    exit 3
    ;;
esac
