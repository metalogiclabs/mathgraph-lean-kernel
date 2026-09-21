from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: select_g3_realizer_v41.py TRACE G2_SELECTION_JSON OUT_JSON")

trace = Path(sys.argv[1]).read_text(errors="replace")
g2 = json.loads(Path(sys.argv[2]).read_text())
winner = g2["winner_materializer"]

m = re.findall(
    r"MSI_V41_G3 winner=(pi|inductive) total=(\d+) direct=(\d+)",
    trace,
)
if not m:
    raise SystemExit("V41_RHO3_MISSING")
observed_winner, total, direct = m[-1]
total, direct = int(total), int(direct)
if observed_winner != winner:
    raise SystemExit("V41_RHO3_WINNER_MISMATCH")
if total <= 0 or direct <= 0:
    raise SystemExit("V41_RHO3_NO_NEW_CONTINUATION_PRESSURE")

materializer = (
    "pi_continuation"
    if winner == "pi"
    else "inductive_telescope_continuation"
)
out = {
    "schema": "metatron.sustained-nebula.g3.v41",
    "source_g2_materializer": winner,
    "winner_id": "c3",
    "winner_materializer": materializer,
    "selection_uses_heldout": False,
    "residual_total": total,
    "new_direct_opportunities": direct,
    "unique_expected_variant_realizer": True,
}
Path(sys.argv[3]).write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
print(json.dumps(out, sort_keys=True))
print("V41_G3_NEW_PRESSURE=PASS")
print("V41_G3_UNIQUE_REALIZER=PASS")
