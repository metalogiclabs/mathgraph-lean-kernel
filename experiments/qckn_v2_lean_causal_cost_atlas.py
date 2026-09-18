from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from realitygraph.capability import FiniteCapability
from realitygraph.compiled_present import CompiledPresent
from realitygraph.ledger import Ledger

from experiments.qckn_v2_lean_compounding import AuthorityEvidence


SCHEMA = "qckn-v2-lean-causal-cost-atlas-v1"
OBSTRUCTION_CODE = "ACTIVATION_COUNT_NOT_COST_CONSEQUENTIAL"
PRIOR_RUN_ID = "35343216790"
PRIOR_CANDIDATE_SHA = "731da4ad2abf1461223a47620fbf584908cdec0f"
SOURCE_WORKLOAD = "perf/beta-ladder"
SOURCE_SPEEDUP_FLOOR = 2.0
SELECTOR_THRESHOLD = 64
ATLAS_THRESHOLDS = (0, 8, 32, 64)
ACTIVATION_RETENTION = {
    0: 1.0,
    8: 0.995998,
    32: 0.983992,
    64: 0.967984,
}
ACTIVATION_SIGNIFICANCE_FLOOR = 0.90
CAUSAL_SAVINGS_SIGNIFICANCE_FLOOR = 0.90
CAPABILITY_ID = "lean-r1-activation-cost-obstruction-v1"
CAPABILITY_INPUT = "ACTIVATION_COUNT_SELECTOR"
CAPABILITY_OUTPUT = "RUN_CAUSAL_COST_ATLAS"


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(payload: Mapping[str, object], *, prefix: str) -> str:
    return hashlib.sha256((prefix + _canonical_json(payload)).encode()).hexdigest()


@dataclass(frozen=True)
class TypedObstruction:
    code: str
    scope: str
    selector_threshold: int
    activation_retention: float
    observed_speedup: float
    required_speedup: float
    counterexample: tuple[int, int]
    authority_snapshot: str
    verifier_id: str
    evidence_digest: str
    first_exact_obstruction: str

    def payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "scope": self.scope,
            "selector_threshold": self.selector_threshold,
            "activation_retention": self.activation_retention,
            "observed_speedup": self.observed_speedup,
            "required_speedup": self.required_speedup,
            "counterexample": {
                "r1_off_callgrind_ir": self.counterexample[0],
                "depth64_callgrind_ir": self.counterexample[1],
            },
            "authority_snapshot": self.authority_snapshot,
            "verifier_id": self.verifier_id,
            "evidence_digest": self.evidence_digest,
            "first_exact_obstruction": self.first_exact_obstruction,
        }

    @property
    def digest(self) -> str:
        return _digest(self.payload(), prefix="lean-red-obstruction-v1:")


@dataclass(frozen=True)
class CompiledRed:
    obstruction: TypedObstruction
    capability: FiniteCapability
    ledger: Ledger
    present: CompiledPresent


@dataclass(frozen=True)
class SearchPlan:
    action: str
    search_calls: int
    used_compiled_obstruction: bool


def load_prior_authority(path: str | Path) -> AuthorityEvidence:
    payload = json.loads(Path(path).read_text())
    authority = AuthorityEvidence.from_mapping(payload)
    if authority.candidate_sha != PRIOR_CANDIDATE_SHA:
        raise ValueError(
            f"prior RED commit changed: {authority.candidate_sha} != {PRIOR_CANDIDATE_SHA}"
        )
    return authority


def compile_prior_red(authority: AuthorityEvidence) -> CompiledRed:
    source = authority.workload_map[SOURCE_WORKLOAD]
    if not source.parity:
        raise ValueError("prior RED lacks exact source parity")
    if source.speedup >= SOURCE_SPEEDUP_FLOOR:
        raise ValueError("authority evidence does not contain the preregistered source RED")

    obstruction = TypedObstruction(
        code=OBSTRUCTION_CODE,
        scope=(
            "lean-r1-direct-beta-fusion/depth-threshold/"
            f"{SOURCE_WORKLOAD}/arena-{authority.arena_sha}"
        ),
        selector_threshold=SELECTOR_THRESHOLD,
        activation_retention=ACTIVATION_RETENTION[SELECTOR_THRESHOLD],
        observed_speedup=source.speedup,
        required_speedup=SOURCE_SPEEDUP_FLOOR,
        counterexample=(source.ablated_ir, source.candidate_ir),
        authority_snapshot=authority.authority_snapshot,
        verifier_id=authority.verifier_id,
        evidence_digest=authority.digest,
        first_exact_obstruction=(
            "SOURCE_COST_GATE_FAILED: perf/beta-ladder speedup "
            f"{source.speedup:.6f} is below {SOURCE_SPEEDUP_FLOOR:.6f}"
        ),
    )
    capability = FiniteCapability(
        capability_id=CAPABILITY_ID,
        input_type="lean-r1-selector-evidence-kind-v1",
        output_type="lean-r1-next-search-v1",
        semantics=((CAPABILITY_INPUT, CAPABILITY_OUTPUT),),
        guard_inputs=(CAPABILITY_INPUT,),
        certificate_id=f"cert:exact-red:{PRIOR_RUN_ID}:{obstruction.digest}",
        dependencies=(),
        authority_snapshot=authority.authority_snapshot,
        verifier_id=authority.verifier_id,
        provenance_ids=(
            f"github-actions-run:{PRIOR_RUN_ID}",
            f"authority-evidence:{authority.digest}",
            f"typed-obstruction:{obstruction.digest}",
        ),
        cost=1,
    )
    ledger = Ledger()
    ledger.append_promote_capability(capability, kernel=SCHEMA)
    present = ledger.materialize_compiled_present().restart()
    return CompiledRed(obstruction, capability, ledger, present)


def plan_next_search(present: CompiledPresent | None) -> SearchPlan:
    if present is not None:
        graph = present.capability_graph
        if CAPABILITY_ID in graph.active_ids():
            capability = graph.capability_map[CAPABILITY_ID]
            return SearchPlan(
                action=capability.execute(CAPABILITY_INPUT),
                search_calls=0,
                used_compiled_obstruction=True,
            )
    return SearchPlan(
        action=CAPABILITY_OUTPUT,
        search_calls=1,
        used_compiled_obstruction=False,
    )


@dataclass(frozen=True)
class AtlasMeasurement:
    status: int
    parity_digest: str
    callgrind_ir: int


@dataclass(frozen=True)
class AtlasRow:
    threshold: int
    callgrind_ir: int
    speedup: float
    activation_retention: float
    causal_savings_retention: float

    def payload(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "callgrind_ir": self.callgrind_ir,
            "speedup": self.speedup,
            "activation_retention": self.activation_retention,
            "causal_savings_retention": self.causal_savings_retention,
        }


@dataclass(frozen=True)
class AtlasResult:
    verdict: str
    off_callgrind_ir: int
    rows: dict[int, AtlasRow]

    def payload(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "verdict": self.verdict,
            "cost_unit": "callgrind-instructions",
            "source_workload": SOURCE_WORKLOAD,
            "off_callgrind_ir": self.off_callgrind_ir,
            "activation_significance_floor": ACTIVATION_SIGNIFICANCE_FLOOR,
            "causal_savings_significance_floor": CAUSAL_SAVINGS_SIGNIFICANCE_FLOOR,
            "rows": {
                str(threshold): row.payload()
                for threshold, row in sorted(self.rows.items())
            },
        }


@dataclass(frozen=True)
class CausalCostAtlas:
    off: AtlasMeasurement
    thresholds: tuple[tuple[int, AtlasMeasurement], ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "CausalCostAtlas":
        required = ("off", *(str(value) for value in ATLAS_THRESHOLDS))
        if set(payload) != set(required):
            raise ValueError(f"atlas arms must be exactly {required}")

        def parse(name: str) -> AtlasMeasurement:
            raw = payload[name]
            if not isinstance(raw, Mapping):
                raise ValueError(f"atlas arm must be a mapping: {name}")
            measurement = AtlasMeasurement(
                status=int(raw.get("status", -1)),
                parity_digest=str(raw.get("parity_digest", "")),
                callgrind_ir=int(raw.get("callgrind_ir", 0)),
            )
            if measurement.callgrind_ir <= 0:
                raise ValueError(f"atlas cost must be positive: {name}")
            return measurement

        off = parse("off")
        thresholds = tuple((value, parse(str(value))) for value in ATLAS_THRESHOLDS)
        all_measurements = (off, *(measurement for _, measurement in thresholds))
        if any(item.status != 0 for item in all_measurements) or len(
            {item.parity_digest for item in all_measurements}
        ) != 1:
            raise ValueError("atlas requires exact acceptance/parity across every arm")
        return cls(off, thresholds)

    def analyse(self) -> AtlasResult:
        measurements = dict(self.thresholds)
        unrestricted = measurements[0]
        total_savings = self.off.callgrind_ir - unrestricted.callgrind_ir
        if total_savings <= 0:
            raise ValueError("unrestricted R1 must improve causal source cost")

        rows: dict[int, AtlasRow] = {}
        for threshold, measurement in self.thresholds:
            rows[threshold] = AtlasRow(
                threshold=threshold,
                callgrind_ir=measurement.callgrind_ir,
                speedup=self.off.callgrind_ir / measurement.callgrind_ir,
                activation_retention=ACTIVATION_RETENTION[threshold],
                causal_savings_retention=(
                    self.off.callgrind_ir - measurement.callgrind_ir
                )
                / total_savings,
            )

        depth64 = rows[SELECTOR_THRESHOLD]
        mismatch = (
            depth64.activation_retention >= ACTIVATION_SIGNIFICANCE_FLOOR
            and depth64.causal_savings_retention < CAUSAL_SAVINGS_SIGNIFICANCE_FLOOR
        )
        verdict = "OBSTRUCTION_CONFIRMED" if mismatch else "PRIOR_RED_NOT_REPRODUCED"
        return AtlasResult(verdict, self.off.callgrind_ir, rows)


def load_measurements_tsv(path: str | Path) -> CausalCostAtlas:
    rows = list(csv.DictReader(Path(path).open(), delimiter="\t"))
    by_arm = {row["arm"]: row for row in rows if row["label"] == SOURCE_WORKLOAD}
    payload = {
        arm: {
            "status": int(row["status"]),
            "parity_digest": row["stdout_sha256"],
            "callgrind_ir": int(row["callgrind_ir"]),
        }
        for arm, row in by_arm.items()
    }
    return CausalCostAtlas.from_mapping(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-authority-json", required=True)
    parser.add_argument("--measurements-tsv", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    compiled = compile_prior_red(load_prior_authority(args.prior_authority_json))
    search_plan = plan_next_search(compiled.present.restart())
    result = load_measurements_tsv(args.measurements_tsv).analyse()
    payload = result.payload()
    payload.update(
        {
            "prior_run_id": PRIOR_RUN_ID,
            "prior_candidate_sha": PRIOR_CANDIDATE_SHA,
            "typed_obstruction": compiled.obstruction.payload(),
            "typed_obstruction_digest": compiled.obstruction.digest,
            "compiled_capability_id": compiled.capability.capability_id,
            "compiled_present_digest": compiled.present.digest,
            "next_search": {
                "action": search_plan.action,
                "search_calls": search_plan.search_calls,
                "used_compiled_obstruction": search_plan.used_compiled_obstruction,
            },
        }
    )
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if result.verdict != "OBSTRUCTION_CONFIRMED":
        raise SystemExit("PRIOR_RED_NOT_REPRODUCED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
