from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from realitygraph.capability import FiniteCapability
from realitygraph.capability_graph import CapabilityGraph
from realitygraph.compiled_present import CompiledPresent
from realitygraph.ledger import Ledger
from realitygraph.meta_memory import MetaMemory


SCHEMA = "qckn-v2-lean-shallow-structural-selector-v1"
ARENA_SHA = "510fbfead6f02bed1a0179d01729a6ddf5bfd06d"
CHAIN_THRESHOLDS = (2, 4, 8)
SEARCH_COST_UNIT = "structural-candidate-inspected"
SOURCE = "perf/beta-ladder"
WORKLOADS = (
    SOURCE,
    "perf/magma-list-deep-n21",
    "perf/grind-ring-5",
    "mathlib",
)
SPEEDUP_FLOORS = {
    SOURCE: 2.0,
    "perf/magma-list-deep-n21": 1.01,
    "perf/grind-ring-5": 0.95,
    "mathlib": 0.999,
}
OBSTRUCTION_CODE = "NO_LOCAL_STRUCTURAL_SELECTOR_UNDER_R1_CONTEXT"
CAPABILITY_ID = "lean-r1-chain-structural-selector-v1"
SHALLOW_SAVINGS_RETENTION_FLOOR = 0.90


@dataclass(frozen=True)
class Measurement:
    status: int
    digest: str
    ir: int


@dataclass(frozen=True)
class Selection:
    threshold: int
    search_calls: int
    cost_unit: str = SEARCH_COST_UNIT


@dataclass(frozen=True)
class StructuralDiscovery:
    base8: Measurement
    candidates: tuple[tuple[int, Measurement], ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "StructuralDiscovery":
        required = {"base8", *(f"chain{n}" for n in CHAIN_THRESHOLDS)}
        if set(payload) != required:
            raise ValueError(f"discovery arms must be exactly {sorted(required)}")

        def parse(name: str) -> Measurement:
            raw = payload[name]
            if not isinstance(raw, Mapping):
                raise ValueError(f"measurement must be a mapping: {name}")
            item = Measurement(
                status=int(raw.get("status", -1)),
                digest=str(raw.get("digest", "")),
                ir=int(raw.get("ir", 0)),
            )
            if item.ir <= 0 or not item.digest:
                raise ValueError(f"invalid measurement: {name}")
            return item

        base8 = parse("base8")
        candidates = tuple((n, parse(f"chain{n}")) for n in CHAIN_THRESHOLDS)
        all_items = (base8, *(item for _, item in candidates))
        if any(item.status != 0 for item in all_items) or len(
            {item.digest for item in all_items}
        ) != 1:
            raise ValueError("discovery requires exact acceptance/parity")
        return cls(base8, candidates)

    def select(self) -> Selection:
        unrestricted = dict(self.candidates)[2]
        total_shallow_savings = self.base8.ir - unrestricted.ir
        if total_shallow_savings <= 0:
            raise LookupError(OBSTRUCTION_CODE)
        qualified = [
            (index, threshold)
            for index, (threshold, item) in enumerate(self.candidates, start=1)
            if (self.base8.ir - item.ir) / total_shallow_savings
            >= SHALLOW_SAVINGS_RETENTION_FLOOR
        ]
        if not qualified:
            raise LookupError(OBSTRUCTION_CODE)
        search_calls, threshold = qualified[-1]
        return Selection(threshold=threshold, search_calls=search_calls)

    def payload(self) -> dict[str, object]:
        return {
            "base8": {
                "status": self.base8.status,
                "digest": self.base8.digest,
                "ir": self.base8.ir,
            },
            **{
                f"chain{threshold}": {
                    "status": item.status,
                    "digest": item.digest,
                    "ir": item.ir,
                    "incremental_shallow_savings_retention": (
                        (self.base8.ir - item.ir)
                        / (self.base8.ir - dict(self.candidates)[2].ir)
                    ),
                }
                for threshold, item in self.candidates
            },
        }


@dataclass(frozen=True)
class WorkloadEvidence:
    parity: bool
    off_ir: int
    candidate_ir: int

    @property
    def speedup(self) -> float:
        return self.off_ir / self.candidate_ir


@dataclass(frozen=True)
class StructuralAuthority:
    workloads: tuple[tuple[str, WorkloadEvidence], ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "StructuralAuthority":
        rows: list[tuple[str, WorkloadEvidence]] = []
        for name in WORKLOADS:
            raw = payload.get(name)
            if not isinstance(raw, Mapping):
                raise ValueError(f"missing authority workload: {name}")
            item = WorkloadEvidence(
                parity=bool(raw.get("parity")),
                off_ir=int(raw.get("off_ir", 0)),
                candidate_ir=int(raw.get("candidate_ir", 0)),
            )
            if item.off_ir <= 0 or item.candidate_ir <= 0:
                raise ValueError(f"authority cost must be positive: {name}")
            rows.append((name, item))
        return cls(tuple(rows))

    @property
    def workload_map(self) -> dict[str, WorkloadEvidence]:
        return dict(self.workloads)

    @property
    def digest(self) -> str:
        raw = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def payload(self) -> dict[str, object]:
        return {
            name: {
                "parity": item.parity,
                "off_ir": item.off_ir,
                "candidate_ir": item.candidate_ir,
                "speedup": item.speedup,
            }
            for name, item in self.workloads
        }


@dataclass(frozen=True)
class ProbeResult:
    verdict: str
    first_exact_obstruction: str | None
    selected_threshold: int | None
    promoted_capability_id: str | None
    cold_search_calls: int
    warm_search_calls: int
    raw_history_search_calls: int
    sham_search_calls: int
    ablation_search_calls: int
    active_before: int
    active_after: int
    restart_exact: bool
    compiled_present_digest: str | None
    discovery: StructuralDiscovery
    authority: StructuralAuthority | None

    def payload(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "verdict": self.verdict,
            "first_exact_obstruction": self.first_exact_obstruction,
            "selector_family": "consecutive-recurrent-beta-chain-length",
            "selector_scope": "depth-0-through-7-only; depth-8-plus retained",
            "selector_portfolio": list(CHAIN_THRESHOLDS),
            "selected_threshold": self.selected_threshold,
            "search_cost_unit": SEARCH_COST_UNIT,
            "search_calls": {
                "COLD": self.cold_search_calls,
                "WARM": self.warm_search_calls,
                "RAW_HISTORY": self.raw_history_search_calls,
                "SHAM": self.sham_search_calls,
                "ANCESTOR_ABLATION": self.ablation_search_calls,
            },
            "promoted_capability_id": self.promoted_capability_id,
            "active": {"before": self.active_before, "after": self.active_after},
            "restart_exact": self.restart_exact,
            "compiled_present_digest": self.compiled_present_digest,
            "discovery": self.discovery.payload(),
            "authority": None if self.authority is None else self.authority.payload(),
        }


def _red(
    discovery: StructuralDiscovery,
    obstruction: str,
    authority: StructuralAuthority | None = None,
    selected: Selection | None = None,
) -> ProbeResult:
    cold = len(CHAIN_THRESHOLDS) if selected is None else selected.search_calls
    return ProbeResult(
        verdict="RED",
        first_exact_obstruction=obstruction,
        selected_threshold=None if selected is None else selected.threshold,
        promoted_capability_id=None,
        cold_search_calls=cold,
        warm_search_calls=cold,
        raw_history_search_calls=cold,
        sham_search_calls=cold,
        ablation_search_calls=cold,
        active_before=0,
        active_after=0,
        restart_exact=False,
        compiled_present_digest=None,
        discovery=discovery,
        authority=authority,
    )


def evaluate_probe(
    discovery: StructuralDiscovery,
    authority: StructuralAuthority | None,
) -> ProbeResult:
    try:
        selected = discovery.select()
    except LookupError:
        return _red(discovery, OBSTRUCTION_CODE)

    if authority is None:
        return _red(discovery, "AUTHORITY_EVIDENCE_MISSING", selected=selected)

    for name in WORKLOADS:
        item = authority.workload_map[name]
        if not item.parity:
            return _red(
                discovery,
                f"SEMANTIC_PARITY_FAILED: {name}",
                authority,
                selected,
            )
        if item.speedup < SPEEDUP_FLOORS[name]:
            code = {
                SOURCE: "SOURCE_COST_GATE_FAILED",
                "perf/magma-list-deep-n21": "HELDOUT_COST_GATE_FAILED",
                "perf/grind-ring-5": "GRIND_COST_GATE_FAILED",
                "mathlib": "MATHLIB_COST_GATE_FAILED",
            }[name]
            return _red(
                discovery,
                f"{code}: {name} speedup {item.speedup:.6f} is below {SPEEDUP_FLOORS[name]:.6f}",
                authority,
                selected,
            )

    ancestor = FiniteCapability(
        capability_id="lean-r1-structural-search-plan-v1",
        input_type="lean-r1-red-obstruction",
        output_type="lean-r1-search-family",
        semantics=(("ACTIVATION_COUNT_NOT_COST_CONSEQUENTIAL", "CHAIN_LENGTH"),),
        guard_inputs=("ACTIVATION_COUNT_NOT_COST_CONSEQUENTIAL",),
        certificate_id="cert:causal-cost-atlas:35378475530",
        dependencies=(),
        authority_snapshot="qckn-v2-lean-causal-cost-atlas-v1-frozen@065e12d",
        verifier_id="lean-callgrind-exact-causal-atlas-v1",
        provenance_ids=("actions-run:35378475530",),
        cost=1,
    )
    standalone = FiniteCapability(
        capability_id=CAPABILITY_ID,
        input_type="lean-r1-local-structure",
        output_type="lean-r1-decision",
        semantics=tuple(
            (f"chain-at-least-{threshold}", "ENABLE" if threshold >= selected.threshold else "DISABLE")
            for threshold in CHAIN_THRESHOLDS
        ),
        guard_inputs=tuple(f"chain-at-least-{threshold}" for threshold in CHAIN_THRESHOLDS),
        certificate_id=f"cert:lean-r1-chain-authority:{authority.digest[:16]}",
        dependencies=(),
        authority_snapshot=f"lean-kernel-arena@{ARENA_SHA}",
        verifier_id="lean-kernel-arena-callgrind-exact-structural-v1",
        provenance_ids=(ancestor.capability_id, ancestor.certificate_id, authority.digest),
        cost=1,
    )
    ledger = Ledger()
    parent = ledger.append_promote_capability(ancestor, SCHEMA, parents=())
    ledger.append_promote_capability(standalone, SCHEMA, parents=(parent.id,))
    present = CompiledPresent.compile(
        CapabilityGraph((standalone,)), MetaMemory.empty()
    )
    restarted = present.restart()
    restart_exact = restarted.text() == present.text() and restarted.digest == present.digest
    trusted = (
        CAPABILITY_ID in restarted.capability_graph.active_ids()
        and restarted.capability_graph.capability_map[CAPABILITY_ID].certificate_id
        == standalone.certificate_id
    )
    empty = CompiledPresent.compile(CapabilityGraph(()), MetaMemory.empty()).restart()
    ablated_trusted = CAPABILITY_ID in empty.capability_graph.active_ids()
    return ProbeResult(
        verdict="GREEN",
        first_exact_obstruction=None,
        selected_threshold=selected.threshold,
        promoted_capability_id=CAPABILITY_ID,
        cold_search_calls=selected.search_calls,
        warm_search_calls=0 if trusted else selected.search_calls,
        raw_history_search_calls=selected.search_calls,
        sham_search_calls=selected.search_calls,
        ablation_search_calls=0 if ablated_trusted else selected.search_calls,
        active_before=2,
        active_after=len(restarted.capability_graph.active_ids()),
        restart_exact=restart_exact,
        compiled_present_digest=restarted.digest,
        discovery=discovery,
        authority=authority,
    )


def _read_tsv(path: Path) -> tuple[StructuralDiscovery, StructuralAuthority | None]:
    rows = list(csv.DictReader(path.open(), delimiter="\t"))
    by = {(row["label"], row["arm"]): row for row in rows}

    def measurement(label: str, arm: str) -> dict[str, object]:
        row = by[(label, arm)]
        return {
            "status": int(row["status"]),
            "digest": row["stdout_sha256"],
            "ir": int(row["callgrind_ir"]),
        }

    discovery = StructuralDiscovery.from_mapping(
        {
            "base8": measurement(SOURCE, "base8"),
            **{
                f"chain{threshold}": measurement(SOURCE, f"chain{threshold}")
                for threshold in CHAIN_THRESHOLDS
            },
        }
    )
    try:
        selected = discovery.select()
    except LookupError:
        return discovery, None
    candidate = f"chain{selected.threshold}"
    authority = StructuralAuthority.from_mapping(
        {
            name: {
                "parity": (
                    by[(name, "off")]["status"] == "0"
                    and by[(name, candidate)]["status"] == "0"
                    and by[(name, "off")]["stdout_sha256"]
                    == by[(name, candidate)]["stdout_sha256"]
                ),
                "off_ir": int(by[(name, "off")]["callgrind_ir"]),
                "candidate_ir": int(by[(name, candidate)]["callgrind_ir"]),
            }
            for name in WORKLOADS
        }
    )
    return discovery, authority


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements-tsv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    discovery, authority = _read_tsv(args.measurements_tsv)
    result = evaluate_probe(discovery, authority)
    args.output.write_text(json.dumps(result.payload(), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
