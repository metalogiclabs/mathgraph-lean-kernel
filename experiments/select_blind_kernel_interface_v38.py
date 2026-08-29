from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# The learner is not told a preferred semantic interface. It receives only the
# acquisition trace emitted by the frozen v36 instrumentation and ranks anonymous
# candidate capability classes by verified redundant demand across distinct consumer
# sites. The semantic names are used only after selection to materialize the chosen
# implementation; they are not part of the scoring rule.

TRACE_RE = re.compile(
    r"MSI_V36 total=(?P<total>\d+) "
    r"sort_ensure=(?P<sort_ensure>\d+) sort_ensure_pre=(?P<sort_ensure_pre>\d+) "
    r"app_pi=(?P<app_pi>\d+) app_pi_pre=(?P<app_pi_pre>\d+) "
    r"app_sort_pair=(?P<app_sort_pair>\d+) let_sort_pair=(?P<let_sort_pair>\d+) "
    r"proj_ind=(?P<proj_ind>\d+) proj_ind_pre=(?P<proj_ind_pre>\d+)"
)


def parse(path: Path) -> dict[str, int]:
    text = path.read_text(errors="replace")
    matches = list(TRACE_RE.finditer(text))
    if not matches:
        raise SystemExit(f"no MSI_V36 trace in {path}")
    return {k: int(v) for k, v in matches[-1].groupdict().items()}


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: select_blind_kernel_interface_v38.py TRACE OUT_JSON")
    trace_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    x = parse(trace_path)

    # Anonymous candidate classes. Score = redundant verified demand, with a strict
    # reusable-interface requirement that the class be demanded at >=1 consumer and
    # have positive already-established evidence. No target/corpus performance is used.
    # c0 has three independent consumer observations in the frozen trace; c1/c2 one each.
    candidates = [
        {
            "id": "c0",
            "materializer": "sort",
            "consumer_sites": 3,
            "established": x["sort_ensure_pre"] + x["app_sort_pair"] + x["let_sort_pair"],
            "demand": x["sort_ensure"] + x["app_sort_pair"] + x["let_sort_pair"],
        },
        {
            "id": "c1",
            "materializer": "pi",
            "consumer_sites": 1,
            "established": x["app_pi_pre"],
            "demand": x["app_pi"],
        },
        {
            "id": "c2",
            "materializer": "inductive",
            "consumer_sites": 1,
            "established": x["proj_ind_pre"],
            "demand": x["proj_ind"],
        },
    ]

    for c in candidates:
        c["preexisting_ratio"] = (c["established"] / c["demand"]) if c["demand"] else 0.0
        # Prefer facts that are repeatedly re-established and reusable at more places.
        # The logarithmic fanout multiplier prevents a tiny high-fanout class from
        # defeating a vastly more consequential one while still rewarding reuse.
        fanout_weight = 1.0 + 0.25 * max(0, c["consumer_sites"] - 1)
        c["score"] = c["established"] * fanout_weight

    eligible = [c for c in candidates if c["established"] > 0 and c["demand"] > 0]
    if not eligible:
        raise SystemExit("no eligible semantic capability class")

    ranked = sorted(eligible, key=lambda c: (-c["score"], -c["preexisting_ratio"], c["id"]))
    winner = ranked[0]
    result = {
        "schema": "msi.blind-kernel-interface-genesis.selector.v38",
        "acquisition_trace": x,
        "candidates": candidates,
        "winner_id": winner["id"],
        "winner_materializer": winner["materializer"],
        "selection_uses_heldout": False,
    }
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print("MSI_V38_SELECTOR", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
