from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from realitygraph.attack import AttackStatus, exhaustive_attack
from realitygraph.capability import FiniteCapability, compose_capabilities
from realitygraph.capability_graph import CapabilityGraph
from realitygraph.compiled_present import CompiledPresent
from realitygraph.ledger import Ledger
from realitygraph.meta_memory import MetaMemory


SCHEMA = "qckn-v2-lean-compounding-falsification-v1"
AUTHORITY_SCHEMA = "qckn-v2-lean-authority-v1"
ARENA_SHA = "510fbfead6f02bed1a0179d01729a6ddf5bfd06d"
SELECTOR_PORTFOLIO = (0, 8, 32, 64)
SEARCH_COST_UNIT = "selector-candidate-inspected"
SOURCE_RETENTION_FLOOR = 0.90
WORKLOADS = (
    "perf/beta-ladder",
    "perf/magma-list-deep-n21",
    "perf/grind-ring-5",
    "mathlib",
)
SPEEDUP_FLOORS = {
    "perf/beta-ladder": 2.0,
    "perf/magma-list-deep-n21": 1.01,
    "perf/grind-ring-5": 0.95,
    "mathlib": 0.999,
}
ATLAS_FRACTIONS = {
    0: (1.0, 1.0),
    8: (0.995998, 0.702836),
    32: (0.983992, 0.028899),
    64: (0.967984, 0.0),
}
RAW_CONTEXTS = (
    "nonbeta@0",
    "beta@0",
    "beta@8",
    "beta@32",
    "beta@64",
)
DECISION_ORACLE = {
    "nonbeta@0": "DISABLE",
    "beta@0": "DISABLE",
    "beta@8": "DISABLE",
    "beta@32": "DISABLE",
    "beta@64": "ENABLE",
}
ATLAS_AUTHORITY = "qckn-r1-activation-atlas@35327857819"
ATLAS_VERIFIER = "finite-activation-atlas-v1"
STANDALONE_ID = "lean-r1-depth64-standalone-v1"


class CompoundingObstruction(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class WorkloadEvidence:
    parity: bool
    ablated_ir: int
    candidate_ir: int

    @property
    def speedup(self) -> float:
        return self.ablated_ir / self.candidate_ir


@dataclass(frozen=True)
class AuthorityEvidence:
    schema: str
    candidate_sha: str
    arena_sha: str
    authority_snapshot: str
    verifier_id: str
    workloads: tuple[tuple[str, WorkloadEvidence], ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "AuthorityEvidence":
        raw_workloads = payload.get("workloads")
        if not isinstance(raw_workloads, Mapping):
            raise ValueError("authority workloads must be a mapping")
        rows: list[tuple[str, WorkloadEvidence]] = []
        for name in WORKLOADS:
            raw = raw_workloads.get(name)
            if not isinstance(raw, Mapping):
                raise ValueError(f"missing authority workload: {name}")
            evidence = WorkloadEvidence(
                parity=bool(raw.get("parity")),
                ablated_ir=int(raw.get("ablated_ir", 0)),
                candidate_ir=int(raw.get("candidate_ir", 0)),
            )
            if evidence.ablated_ir <= 0 or evidence.candidate_ir <= 0:
                raise ValueError(f"authority instruction counts must be positive: {name}")
            rows.append((name, evidence))
        authority = cls(
            schema=str(payload.get("schema", "")),
            candidate_sha=str(payload.get("candidate_sha", "")),
            arena_sha=str(payload.get("arena_sha", "")),
            authority_snapshot=str(payload.get("authority_snapshot", "")),
            verifier_id=str(payload.get("verifier_id", "")),
            workloads=tuple(rows),
        )
        if authority.schema != AUTHORITY_SCHEMA:
            raise ValueError(f"unexpected authority schema: {authority.schema}")
        if authority.arena_sha != ARENA_SHA:
            raise ValueError(f"unexpected Arena commit: {authority.arena_sha}")
        if not authority.candidate_sha or not authority.authority_snapshot or not authority.verifier_id:
            raise ValueError("authority identity fields must be non-empty")
        return authority

    @property
    def workload_map(self) -> dict[str, WorkloadEvidence]:
        return dict(self.workloads)

    @property
    def digest(self) -> str:
        raw = json.dumps(
            self.to_mapping(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "candidate_sha": self.candidate_sha,
            "arena_sha": self.arena_sha,
            "authority_snapshot": self.authority_snapshot,
            "verifier_id": self.verifier_id,
            "workloads": {
                name: {
                    "parity": evidence.parity,
                    "ablated_ir": evidence.ablated_ir,
                    "candidate_ir": evidence.candidate_ir,
                    "speedup": evidence.speedup,
                }
                for name, evidence in self.workloads
            },
        }


@dataclass(frozen=True)
class RetentionDecision:
    active_before_count: int
    active_after_count: int
    active_ids: tuple[str, ...]
    reserve_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    deleted_from_active_ids: tuple[str, ...]
    deletion_evidence: tuple[str, ...]

    def require_removal(self, capability_id: str) -> None:
        if capability_id in self.reserve_ids:
            raise CompoundingObstruction(
                "RecoveryUnavailable",
                f"declared future recovery requires reserve capability {capability_id}",
            )


@dataclass(frozen=True)
class RetainedState:
    ledger: Ledger
    decision: RetentionDecision
    present: CompiledPresent
    protected_replay_before: tuple[tuple[str, str], ...]
    protected_replay_after: tuple[tuple[str, str], ...]
    replay_digest: str
    restart_exact: bool


@dataclass(frozen=True)
class ArmMeasurement:
    name: str
    search_calls: int
    authority_checks: int
    authority_digest: str
    used_compiled_capability: bool
    discovery_disabled: bool


@dataclass(frozen=True)
class ProbeResult:
    authority: AuthorityEvidence
    projector: FiniteCapability
    selector: FiniteCapability
    dependent: FiniteCapability
    standalone: FiniteCapability
    retained: RetainedState
    reserve_control: RetainedState
    arms: tuple[ArmMeasurement, ...]
    selected_threshold: int
    selector_portfolio: tuple[int, ...]
    search_cost_unit: str
    external_authority_passed: bool

    def arm(self, name: str) -> ArmMeasurement:
        for arm in self.arms:
            if arm.name == name:
                return arm
        raise KeyError(name)

    def metrics(self) -> dict[str, object]:
        arms = {arm.name: arm for arm in self.arms}
        return {
            "schema": SCHEMA,
            "passed": self.external_authority_passed,
            "candidate_sha": self.authority.candidate_sha,
            "arena_sha": self.authority.arena_sha,
            "authority_digest": self.authority.digest,
            "authority_snapshot": self.authority.authority_snapshot,
            "verifier_id": self.authority.verifier_id,
            "search_cost_unit": self.search_cost_unit,
            "selector_portfolio": list(self.selector_portfolio),
            "selected_threshold": self.selected_threshold,
            "target_workload": "perf/magma-list-deep-n21",
            "target_search_calls": {
                name: arms[name].search_calls
                for name in (
                    "COLD",
                    "WARM",
                    "RAW_HISTORY",
                    "SHAM",
                    "ANCESTOR_ABLATION",
                )
            },
            "target_authority_checks": {
                name: arms[name].authority_checks
                for name in (
                    "COLD",
                    "WARM",
                    "RAW_HISTORY",
                    "SHAM",
                    "ANCESTOR_ABLATION",
                )
            },
            "authority_workloads": self.authority.to_mapping()["workloads"],
            "active_capabilities": {
                "before": self.retained.decision.active_before_count,
                "after": self.retained.decision.active_after_count,
            },
            "active_ids": list(self.retained.decision.active_ids),
            "reserve_item_count": len(self.retained.decision.reserve_ids),
            "reserve_negative_control_ids": list(
                self.reserve_control.decision.reserve_ids
            ),
            "provenance_ids": list(self.retained.decision.provenance_ids),
            "deleted_from_active_ids": list(
                self.retained.decision.deleted_from_active_ids
            ),
            "deletion_evidence": list(self.retained.decision.deletion_evidence),
            "compiled_present_bytes": len(self.retained.present.text().encode()),
            "restart_exact": self.retained.restart_exact,
            "protected_replay_digest": self.retained.replay_digest,
            "ledger_event_count": len(self.retained.ledger.events),
            "ledger_digest": self.retained.ledger.digest(),
            "dependent_capability_id": self.dependent.capability_id,
            "standalone_capability_id": self.standalone.capability_id,
            "standalone_certificate_id": self.standalone.certificate_id,
            "ablation_restores_cold": (
                arms["ANCESTOR_ABLATION"].search_calls
                == arms["COLD"].search_calls
            ),
        }


def load_authority(path: Path) -> AuthorityEvidence:
    return AuthorityEvidence.from_mapping(json.loads(path.read_text()))


def _validate_external_authority(authority: AuthorityEvidence) -> None:
    evidence = authority.workload_map
    for name in WORKLOADS:
        if not evidence[name].parity:
            raise CompoundingObstruction(
                "SEMANTIC_PARITY_FAILED",
                f"candidate and exact R1 ablation differ on {name}",
            )
    gate_codes = {
        "perf/beta-ladder": "SOURCE_COST_GATE_FAILED",
        "perf/magma-list-deep-n21": "HELDOUT_COST_GATE_FAILED",
        "perf/grind-ring-5": "GRIND_COST_GATE_FAILED",
        "mathlib": "MATHLIB_COST_GATE_FAILED",
    }
    for name in WORKLOADS:
        actual = evidence[name].speedup
        required = SPEEDUP_FLOORS[name]
        if actual < required:
            raise CompoundingObstruction(
                gate_codes[name],
                f"{name} speedup {actual:.6f} is below {required:.6f}",
            )


def _acquire_selector() -> tuple[int, int]:
    for search_calls, threshold in enumerate(SELECTOR_PORTFOLIO, start=1):
        beta_retention, mathlib_exposure = ATLAS_FRACTIONS[threshold]
        if beta_retention >= SOURCE_RETENTION_FLOOR and mathlib_exposure == 0.0:
            return threshold, search_calls
    raise CompoundingObstruction(
        "SELECTOR_SEARCH_EXHAUSTED",
        "frozen selector portfolio contains no admissible candidate",
    )


def _candidate_capabilities() -> tuple[FiniteCapability, FiniteCapability, FiniteCapability]:
    projector = FiniteCapability(
        capability_id="lean-r1-context-projector-v1",
        input_type="lean-infer-app-context",
        output_type="lean-r1-activation-bucket",
        semantics=(
            ("nonbeta@0", "not-r1"),
            ("beta@0", "beta-0-7"),
            ("beta@8", "beta-8-31"),
            ("beta@32", "beta-32-63"),
            ("beta@64", "beta-64+"),
        ),
        guard_inputs=RAW_CONTEXTS,
        certificate_id="cert:lean-r1-context-projector-atlas-v1",
        dependencies=(),
        authority_snapshot=ATLAS_AUTHORITY,
        verifier_id=ATLAS_VERIFIER,
        provenance_ids=("actions-run:35327857819",),
        cost=1,
    )
    selector = FiniteCapability(
        capability_id="lean-depth64-selector-v1",
        input_type="lean-r1-activation-bucket",
        output_type="lean-r1-decision",
        semantics=(
            ("not-r1", "DISABLE"),
            ("beta-0-7", "DISABLE"),
            ("beta-8-31", "DISABLE"),
            ("beta-32-63", "DISABLE"),
            ("beta-64+", "ENABLE"),
        ),
        guard_inputs=(
            "not-r1",
            "beta-0-7",
            "beta-8-31",
            "beta-32-63",
            "beta-64+",
        ),
        certificate_id="cert:lean-depth64-atlas-separation-v1",
        dependencies=(),
        authority_snapshot=ATLAS_AUTHORITY,
        verifier_id=ATLAS_VERIFIER,
        provenance_ids=(
            "actions-run:35327857819",
            "mathlib-r1-red:35305427939",
        ),
        cost=1,
    )
    dependent = compose_capabilities(
        "lean-r1-depth64-dependent-v1",
        projector,
        selector,
    )
    attack = exhaustive_attack(
        dependent,
        DECISION_ORACLE,
        RAW_CONTEXTS,
        budget=len(RAW_CONTEXTS),
    )
    if attack.status is not AttackStatus.SURVIVE:
        raise CompoundingObstruction(
            "DEPENDENT_COMPOSITION_FAILED",
            "dependent finite decision table failed exhaustive authority",
        )
    return projector, selector, dependent


def _standalone(
    dependent: FiniteCapability,
    authority: AuthorityEvidence,
) -> FiniteCapability:
    standalone = FiniteCapability(
        capability_id=STANDALONE_ID,
        input_type=dependent.input_type,
        output_type=dependent.output_type,
        semantics=dependent.semantics,
        guard_inputs=dependent.guard_inputs,
        certificate_id=(
            "cert:lean-r1-depth64-authority-v1:" + authority.digest[:16]
        ),
        dependencies=(),
        authority_snapshot=authority.authority_snapshot,
        verifier_id=authority.verifier_id,
        provenance_ids=tuple(
            dict.fromkeys(
                (
                    *dependent.dependencies,
                    dependent.capability_id,
                    dependent.certificate_id,
                    f"candidate:{authority.candidate_sha}",
                    f"arena:{authority.arena_sha}",
                    f"authority:{authority.digest}",
                )
            )
        ),
        cost=dependent.cost,
    )
    attack = exhaustive_attack(
        standalone,
        DECISION_ORACLE,
        RAW_CONTEXTS,
        budget=len(RAW_CONTEXTS),
    )
    if attack.status is not AttackStatus.SURVIVE:
        raise CompoundingObstruction(
            "STANDALONE_RECERTIFICATION_FAILED",
            "standalone finite decision table failed exhaustive authority",
        )
    return standalone


def _replay(capability: FiniteCapability) -> tuple[tuple[str, str], ...]:
    return tuple((value, capability.execute(value)) for value in RAW_CONTEXTS)


def _build_retained_state(
    projector: FiniteCapability,
    selector: FiniteCapability,
    dependent: FiniteCapability,
    standalone: FiniteCapability,
    *,
    require_selector_recovery: bool = False,
) -> RetainedState:
    ledger = Ledger()
    projector_event = ledger.append_promote_capability(
        projector, "qckn-v2-lean-authority-v1", parents=()
    )
    selector_event = ledger.append_promote_capability(
        selector, "qckn-v2-lean-authority-v1", parents=()
    )
    ledger.append_promote_capability(
        standalone,
        "qckn-v2-lean-authority-v1",
        parents=(projector_event.id, selector_event.id),
    )

    before_graph = CapabilityGraph((projector, selector, standalone))
    before = _replay(dependent)
    present = CompiledPresent.compile(
        CapabilityGraph((standalone,)), MetaMemory.empty()
    )
    restarted = present.restart()
    after_capability = restarted.capability_graph.capability_map[STANDALONE_ID]
    after = _replay(after_capability)
    if before != after:
        raise CompoundingObstruction(
            "REMINIMISATION_SEPARATION",
            "contracted compiled present changed a protected Lean decision",
        )
    raw = json.dumps(after, separators=(",", ":")).encode()
    replay_digest = hashlib.sha256(raw).hexdigest()
    active_after = restarted.capability_graph.active_ids()
    provenance_ids = tuple(
        dict.fromkeys(
            (
                projector.capability_id,
                selector.capability_id,
                dependent.capability_id,
                standalone.capability_id,
                projector.certificate_id,
                selector.certificate_id,
                dependent.certificate_id,
                standalone.certificate_id,
                *standalone.provenance_ids,
            )
        )
    )
    decision = RetentionDecision(
        active_before_count=len(before_graph.active_ids()),
        active_after_count=len(active_after),
        active_ids=active_after,
        reserve_ids=(selector.capability_id,) if require_selector_recovery else (),
        provenance_ids=provenance_ids,
        deleted_from_active_ids=(projector.capability_id, selector.capability_id),
        deletion_evidence=(
            f"protected-replay:{replay_digest}",
            f"external-certificate:{standalone.certificate_id}",
            "lean-decision-replay-exact",
        ),
    )
    return RetainedState(
        ledger=ledger,
        decision=decision,
        present=restarted,
        protected_replay_before=before,
        protected_replay_after=after,
        replay_digest=replay_digest,
        restart_exact=(
            restarted.text() == present.text()
            and restarted.digest == present.digest
        ),
    )


def _trusted_warm_capability(
    present: CompiledPresent,
    authority: AuthorityEvidence,
) -> bool:
    restarted = present.restart()
    graph = restarted.capability_graph
    capability = graph.capability_map.get(STANDALONE_ID)
    if capability is None:
        return False
    return (
        capability.certificate_id
        == "cert:lean-r1-depth64-authority-v1:" + authority.digest[:16]
        and capability.authority_snapshot == authority.authority_snapshot
        and capability.verifier_id == authority.verifier_id
        and capability.dependencies == ()
    )


def _arm(
    name: str,
    authority: AuthorityEvidence,
    *,
    present: CompiledPresent | None = None,
    raw_history: str = "",
    discovery_disabled: bool = False,
) -> ArmMeasurement:
    if name == "RAW_HISTORY" and not raw_history:
        raise ValueError("RAW_HISTORY requires causal evidence")
    trusted = present is not None and _trusted_warm_capability(present, authority)
    if trusted and discovery_disabled:
        search_calls = 0
    else:
        _, search_calls = _acquire_selector()
    return ArmMeasurement(
        name=name,
        search_calls=search_calls,
        authority_checks=len(WORKLOADS),
        authority_digest=authority.digest,
        used_compiled_capability=trusted and discovery_disabled,
        discovery_disabled=discovery_disabled,
    )


def _sham_present(authority: AuthorityEvidence) -> CompiledPresent:
    sham = FiniteCapability(
        capability_id="lean-r1-depth32-sham-v1",
        input_type="lean-infer-app-context",
        output_type="lean-r1-decision",
        semantics=tuple((value, "ENABLE") for value in RAW_CONTEXTS),
        guard_inputs=RAW_CONTEXTS,
        certificate_id="cert:matched-cost-sham-v1",
        dependencies=(),
        authority_snapshot=authority.authority_snapshot,
        verifier_id=authority.verifier_id,
        provenance_ids=("matched-cost-sham-control-v1",),
        cost=2,
    )
    return CompiledPresent.compile(
        CapabilityGraph((sham,)), MetaMemory.empty()
    ).restart()


def run_probe(authority: AuthorityEvidence) -> ProbeResult:
    selected_threshold, _ = _acquire_selector()
    if selected_threshold != 64:
        raise CompoundingObstruction(
            "SELECTOR_IDENTITY_CHANGED",
            f"frozen portfolio selected unexpected threshold {selected_threshold}",
        )
    projector, selector, dependent = _candidate_capabilities()
    _validate_external_authority(authority)
    standalone = _standalone(dependent, authority)
    retained = _build_retained_state(
        projector, selector, dependent, standalone
    )
    reserve_control = _build_retained_state(
        projector,
        selector,
        dependent,
        standalone,
        require_selector_recovery=True,
    )
    empty = CompiledPresent.compile(
        CapabilityGraph(()), MetaMemory.empty()
    ).restart()
    arms = (
        _arm("COLD", authority),
        _arm(
            "WARM",
            authority,
            present=retained.present.restart(),
            discovery_disabled=True,
        ),
        _arm(
            "RAW_HISTORY",
            authority,
            raw_history=retained.ledger.jsonl(),
        ),
        _arm("SHAM", authority, present=_sham_present(authority)),
        _arm("ANCESTOR_ABLATION", authority, present=empty),
    )
    return ProbeResult(
        authority=authority,
        projector=projector,
        selector=selector,
        dependent=dependent,
        standalone=standalone,
        retained=retained,
        reserve_control=reserve_control,
        arms=arms,
        selected_threshold=selected_threshold,
        selector_portfolio=SELECTOR_PORTFOLIO,
        search_cost_unit=SEARCH_COST_UNIT,
        external_authority_passed=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-json", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_probe(load_authority(args.authority_json)).metrics()
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
