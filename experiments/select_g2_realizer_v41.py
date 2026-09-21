from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: select_g2_realizer_v41.py TRACE OUT_JSON")

text = Path(sys.argv[1]).read_text(errors="replace")
matches = list(re.finditer(
    r"MSI_V41_G2 app_pi=(\d+) app_pi_pre=(\d+) proj_ind=(\d+) proj_ind_pre=(\d+)",
    text,
))
if not matches:
    raise SystemExit("V41_RHO2_MISSING")

app_pi, app_pi_pre, proj_ind, proj_ind_pre = map(int, matches[-1].groups())
candidates = {
    "c1": {
        "materializer": "pi",
        "total": app_pi,
        "pre": app_pi_pre,
    },
    "c2": {
        "materializer": "inductive",
        "total": proj_ind,
        "pre": proj_ind_pre,
    },
}
for item in candidates.values():
    item["gap"] = item["total"] - item["pre"]

eligible = {k:v for k,v in candidates.items() if v["gap"] > 0}
if not eligible:
    raise SystemExit("V41_RHO2_HAS_NO_ADMISSIBLE_REALIZER")

ranked = sorted(
    eligible,
    key=lambda k: (-eligible[k]["gap"], -eligible[k]["total"], k),
)
winner = ranked[0]
if len(ranked) > 1:
    a, b = eligible[ranked[0]], eligible[ranked[1]]
    if (a["gap"], a["total"]) == (b["gap"], b["total"]):
        raise SystemExit("V41_G2_UNKNOWN_CHOICE")

out = {
    "schema": "metatron.sustained-nebula.g2.v41",
    "winner_id": winner,
    "winner_materializer": eligible[winner]["materializer"],
    "selection_uses_heldout": False,
    "anonymous_scores": candidates,
}
Path(sys.argv[2]).write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
print(json.dumps(out, sort_keys=True))
print("V41_G2_UNIQUE_REALIZER=PASS")
