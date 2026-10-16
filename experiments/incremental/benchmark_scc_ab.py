#!/usr/bin/env python3
"""Same-host causal A/B of the exact historical full SCC finisher and retained SCC.

Both arms use the SAME source-owned Lean producer, selected proof checker,
authentication bridge, independent full-index oracles, and workload pins.
The only changed executable is index-session, compiled from the two exact
commits. Baseline seeding is excluded and separately measured.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

from qualify_delta import Qualification, paired_economics, write, file_hash

VARIANTS = ("early-definition", "unrelated-definition")
MODES = ("full", "retained")

def canonical_decisions(result):
    return [
        {k: v for k, v in row.items() if k != "evidence_id"}
        for row in result["decisions"]
    ]

def phase(sample, name):
    result = json.loads(Path(sample["result_path"]).read_bytes())
    value = result.get("timings", {}).get(name)
    if type(value) not in (int, float) or value < 0:
        raise ValueError("missing valid timer: " + name)
    return float(value)

def result_at(sample):
    return json.loads(Path(sample["result_path"]).read_bytes())

def make_qualification(args, profile, mode, workloads):
    import argparse as ap
    out = args.out / profile / mode
    return Qualification(ap.Namespace(
        workloads=workloads, producer=args.producer,
        checker=args.checker, indexer=args.indexer,
        index_session=(args.full_index_session if mode == "full"
                       else args.retained_index_session),
        full_checker=args.full_checker,
        authority_key=(args.full_key if mode == "full" else args.retained_key),
        out=out, repetitions=args.repetitions,
    ))

def assert_good_sample(sample):
    if "error" in sample:
        raise ValueError("qualification sample failed: " + sample["error"])
    result = result_at(sample)
    if result.get("status") != "VERIFIED" or not result.get("evidence_id"):
        raise ValueError("missing authenticated accepted result")
    if result.get("checker_result", {}).get("code") != 0:
        raise ValueError("selected proof kernel did not accept")
    if not sample.get("partition_audit") or not sample.get("persisted_acceptance_audit"):
        raise ValueError("independent partition/HMAC audit absent")
    if sample.get("direct_rust", {}).get("returncode") != 0:
        raise ValueError("fresh Rust oracle did not accept")
    return result

def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    if args.full_index_session.resolve() == args.retained_index_session.resolve():
        raise ValueError("A/B binaries must have distinct paths")
    sha_full = file_hash(args.full_index_session)
    sha_retained = file_hash(args.retained_index_session)
    if sha_full == sha_retained:
        raise ValueError("A/B index-session executables are byte-identical")
    baseline = dict(schema="mathgraph.retained-scc.matched-ab.v1",
                    source_sha=args.source_sha, prior_source_sha=args.prior_source_sha,
                    binaries=dict(historical_full=sha_full, retained=sha_retained,
                                  producer=file_hash(args.producer),
                                  checker=file_hash(args.checker),
                                  indexer=file_hash(args.indexer)),
                    comparison="same_host_same_inputs_different_index_session_binary",
                    timing_scope="warm authenticated producer-to-persistence; cold setup excluded",
                    pair_order="deterministic seeded alternating full/retained",
                    correctness_passed=False, completed=False,
                    profiles={}, failures=[])
    write(args.out / "summary.json", baseline)
    for profile, workloads in (("original", args.original_workloads),
                               ("expanded", args.expanded_workloads)):
        q = {mode: make_qualification(args, profile, mode, workloads)
             for mode in MODES}
        ref = {}
        for mode in MODES:
            q[mode].preflight()
            ref[mode] = {variant: q[mode].reference(variant)
                         for variant in ("baseline",) + VARIANTS}
        # Exact native fresh baseline identity must be shared, not just
        # semantically accepted by both adapters.
        if json.dumps(ref["full"], sort_keys=True) != json.dumps(ref["retained"], sort_keys=True):
            raise ValueError("historical/retained initial full-index identities disagree")
        rows = {variant: [] for variant in VARIANTS}
        for rep in range(args.repetitions):
            variant_order = list(VARIANTS)
            random.Random(20261017 + rep).shuffle(variant_order)
            for variant in variant_order:
                arm_order = ("full", "retained") if (
                    (rep + (0 if variant == "early-definition" else 1)) % 2 == 0
                ) else ("retained", "full")
                pair = dict(profile=profile, variant=variant, repetition=rep,
                            order=list(arm_order), arms={})
                for mode in arm_order:
                    sample = q[mode].sample(variant, rep, ref[mode])
                    result = assert_good_sample(sample)
                    typed = result.get("typed_update", {})
                    if mode == "retained" and typed.get("retained_graph_used") is not True:
                        raise ValueError("retained SCC graph not selected for "+variant)
                    if mode == "full" and typed.get("retained_graph_used") is True:
                        raise ValueError("historical full SCC unexpectedly reports retained path")
                    pair["arms"][mode] = dict(
                        elapsed_seconds=sample["apply_wall_seconds"],
                        identity_seconds=phase(sample, "identity_update_seconds"),
                        setup_seconds=sample["setup_wall_seconds"],
                        selected_check_seconds=phase(sample, "checking_seconds"),
                        materialization_seconds=phase(sample, "materialization_and_hash_seconds"),
                        persistence_seconds=phase(sample, "persistence_seconds"),
                        closure_finish_nanoseconds=typed.get("closure_finish_nanoseconds"),
                        recomputed_sccs=typed.get("recomputed_sccs"),
                        reuse_count=result["counts"]["reused"],
                        checked_count=result["counts"]["rechecked"],
                        status=result["status"],
                        export_sha256=result["export_sha256"],
                        decision_hash=hashlib.sha256(
                            json.dumps(canonical_decisions(result), sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest(),
                        snapshot_sha256=sample["snapshot"]["sha256"],
                        independent_fresh_index=True,
                        authenticated_receipt=True,
                        original_cpp_oracles=(
                            {tool: record.get("returncode")
                             for tool, record in sample.get("independent_kernels", {}).items()}
                        ))
                old = pair["arms"]["full"]
                new = pair["arms"]["retained"]
                for k in ("export_sha256", "snapshot_sha256", "reuse_count",
                          "checked_count", "decision_hash", "status"):
                    if old[k] != new[k]:
                        raise ValueError("paired proof/identity mismatch at "+k)
                if old["status"] != "VERIFIED":
                    raise ValueError("paired outcome is not VERIFIED")
                # A baseline-anchored delta may serialize DAG indices in a
                # different byte order from the separately pinned fresh export.
                # Each arm's Qualification.sample() already independently
                # parses the sealed composite and asserts that the *complete*
                # typed identity equals the exact pinned full-export index.
                # Preserve that oracle, rather than imposing false byte parity.
                for mode in MODES:
                    qualified = q[mode].report["gates"]
                    actual = [
                        gate for gate in qualified
                        if gate["name"] == "composite_index_equals_independent_pinned_export:"
                                          + variant + "-" + str(rep)
                    ]
                    if len(actual) != 1 or actual[0]["passed"] is not True:
                        raise ValueError("pinned composite full-index oracle failed")
                if old["export_sha256"] != old["snapshot_sha256"]:
                    raise ValueError("exact sealed composite hash mismatch")
                if rep == 0:
                    for mode in MODES:
                        if pair["arms"][mode]["original_cpp_oracles"] != {
                            "leanchecker": 0, "leanchecker-paranoid": 0
                        }:
                            raise ValueError("independent C++/paranoid oracle disagreement")
                rows[variant].append(pair)
                baseline["profiles"].setdefault(profile, {})[variant] = dict(
                    pairs=rows[variant], complete=False)
                write(args.out / "summary.json", baseline)
        for variant in VARIANTS:
            paired = rows[variant]
            values = [
                dict(apply_wall_seconds=p["arms"]["retained"]["elapsed_seconds"],
                     direct_wall_seconds=p["arms"]["full"]["elapsed_seconds"])
                for p in paired
            ]
            economics = paired_economics(values, seed=20261017)
            if len(paired) != args.repetitions or args.repetitions < 5:
                raise ValueError("incomplete causal A/B paired samples")
            baseline["profiles"][profile][variant] = dict(
                pairs=paired, complete=True,
                economics=economics,
                identity_median_seconds={
                    mode: statistics.median(p["arms"][mode]["identity_seconds"]
                                            for p in paired)
                    for mode in MODES
                },
                wall_median_seconds={
                    mode: statistics.median(p["arms"][mode]["elapsed_seconds"]
                                            for p in paired)
                    for mode in MODES
                },
                setup_median_seconds={
                    mode: statistics.median(p["arms"][mode]["setup_seconds"]
                                            for p in paired)
                    for mode in MODES
                },
                retained_recomputed_scc_median=statistics.median(
                    p["arms"]["retained"]["recomputed_sccs"] for p in paired),
            )
        for mode in MODES:
            q[mode].report["run_completed"] = True
            q[mode].flush()
            if q[mode].report["correctness_passed"] is not True:
                raise ValueError("one arm failed its required independent qualification")
        write(args.out / "summary.json", baseline)

    lines = [
        "# Retained-SCC versus historical full-SCC: paired same-host experiment",
        "",
        "Two exact-source index-session binaries; identical current producer, checker, issuer policy, pinned input, independent oracles.",
        "Warm source→attestation→index→actual selected checking→persistence wall. Cold setup excluded.",
        "",
        "| Workload / edit | Full-index s | Retained SCC s | Retained saving | Wins | 95% ratio interval | Decision |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for profile in ("original", "expanded"):
        for variant in VARIANTS:
            entry = baseline["profiles"][profile][variant]
            e = entry["economics"]
            percent = 100 * (1 - e["median_ratio"])
            ci = e["bootstrap_ratio_interval_95"]
            lines.append(
                f"| {profile} / {variant} | {entry['wall_median_seconds']['full']:.6f} | "
                f"{entry['wall_median_seconds']['retained']:.6f} | {percent:.2f}% | "
                f"{e['paired_wins']}/{e['paired_count']} | [{ci[0]:.5f},{ci[1]:.5f}] | "
                f"{e['status']} |")
    lines += ["", "Both accepted results agree exactly in typed obligation decisions and export SHA;",
              "fresh Rust and mandatory normal/paranoid C++ oracles accept the identical sealed composite.",
              "Separate native/Python full-index parity and authenticated receipt audits pass per arm.",
              "Bootstrap interval describes only these paired finite host observations.",
              "Neither an O(changed-only) lifetime bound nor old-to-new semantic expansion is claimed.",
              "The previous run's speedup versus direct fresh Rust is separate historical evidence.",
              ""]
    baseline["correctness_passed"] = True
    baseline["completed"] = True
    write(args.out / "summary.json", baseline)
    (args.out / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("original-workloads", "expanded-workloads", "producer", "checker",
                 "indexer", "full-index-session", "retained-index-session",
                 "full-checker", "full-key", "retained-key", "out"):
        parser.add_argument("--"+flag, required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--prior-source-sha", required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 5:
        parser.error("A/B economic claims require at least five complete pairs")
    return run(args)

if __name__ == "__main__":
    sys.exit(main())
