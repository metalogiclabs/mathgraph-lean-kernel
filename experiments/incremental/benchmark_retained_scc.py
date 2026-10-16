#!/usr/bin/env python3
"""Same-host causal A/B of the SAME verified producer and SAME index binary.

Only the baseline-SCC reuse switch varies. Producer -> authenticated delta ->
identity -> full selected parser/kernel -> durable receipt is timed as a whole.
Seeding an admitted baseline, cold import, and independent oracles are charged
separately. A shorter SCC phase alone is not an end-to-end speedup.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import traceback

from build_workloads import EDITS
from producer_delta import DeltaSession
from qualify_delta import (
    NAMES, audit_partition, audit_receipt, canonical, command_run,
    configuration, file_hash, fresh_index, paired_economics,
    sealed_snapshot, write,
)

VARIANTS = ("early-definition", "unrelated-definition")
MODES = ("retained", "full")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def one_mode(args, variant, repetition, mode, expected_index, baseline_index,
             sample_dir, oracle_tools):
    """Exactly one signed, source-owned warm transaction per fresh session."""
    root = sample_dir / mode
    root.mkdir(parents=True)
    session = DeltaSession(
        root=root, workloads=args.workloads, producer=args.producer,
        checker=args.checker, indexer=args.indexer,
        index_session=args.index_session, authority_key=args.authority_key,
        index_mode=mode,
    )
    try:
        start = time.perf_counter()
        ready = session.start()
        setup = time.perf_counter() - start
        require(ready["status"] == "READY", "baseline was not initialized")
        require(session.baseline_result["status"] == "VERIFIED",
                "baseline was not independently admitted")

        start = time.perf_counter()
        result = session.apply(
            source_dir=args.workloads / variant / "source",
            patch=EDITS[variant], claimed_names=NAMES[variant])
        wall = time.perf_counter() - start
        require(result.get("status") == "VERIFIED" and result.get("evidence_id"),
                "warm update failed: " + str(result.get("reason", result.get("status"))))
        require(result["producer_provenance"]["identity_finish_mode"] == mode,
                "finish selection missing from authenticated producer provenance")
        update = result["typed_update"]
        require(update.get("finish_mode") == mode, "index daemon mode mismatch")
        require(type(update.get("finish_nanos")) is int and
                0 < update["finish_nanos"] < 600_000_000_000,
                "native SCC finish timing missing or invalid")
        require(type(update.get("recomputed_sccs")) is int,
                "native SCC count missing")
        require(update.get("retained_graph_used") is (mode == "retained"),
                "unexpected SCC full fallback on frozen simple edit")
        require((update["recomputed_sccs"] > 0) == (mode == "retained"),
                "affected SCC count does not match mode")

        snapshot = Path(session.snapshot_path)
        sealed = sealed_snapshot(snapshot)
        require(sealed["sha256"] == result["export_sha256"],
                "sealed exact export hash mismatched")
        # The authenticated delta may use different NDJSON DAG numbering from
        # the ordinary fresh-export serialization. Byte equality is not the
        # criterion for kernel-equivalent declaration identity. Reparse the
        # exact *sealed changed composite* independently, then require its
        # entire typed index to equal the separately pinned full-export index.
        # This detects missing/unreported changes without requiring transport
        # serialization identity.
        composite_index, composite_index_process = fresh_index(
            snapshot, args.indexer, root / "composite-fresh-index")
        require(not composite_index_process["timed_out"] and
                composite_index_process["returncode"] == 0,
                "independent full-index oracle refused delta composite")
        require(canonical(composite_index) == canonical(expected_index),
                "source-owned composite differs from pinned full-export typed identity")
        partition = audit_partition(result, baseline_index, composite_index)
        receipt = audit_receipt(root, result, composite_index, args.authority_key.read_bytes())
        require(receipt["issuer_hmac_valid"] and receipt["all_content_addresses_valid"],
                "persisted receipt not authenticated")
        require(partition["actual_kernel_checked"] == result["counts"]["rechecked"],
                "kernel checked count not independently reproduced")
        require(result["checker_result"]["code"] == 0,
                "actual selected Rust checker rejected valid source")

        # After timing, check the *same* sealed full byte stream with a fresh
        # Rust verifier. On repetition zero, add actual C++ and paranoid C++.
        config = root / "oracle-config.json"
        write(config, configuration(snapshot))
        full_log, _ = command_run(
            [args.full_checker, config], root / "fresh-rust-oracle")
        require(not full_log["timed_out"] and full_log["returncode"] == 0,
                "independent full Rust checker disagrees")
        more_oracles = {}
        if repetition == 0:
            for name, path in oracle_tools.items():
                process, _ = command_run(
                    [path, "--from-export", snapshot], root / ("oracle-" + name))
                require(not process["timed_out"] and process["returncode"] == 0,
                        name + " independent checker disagrees")
                more_oracles[name] = dict(returncode=process["returncode"],
                                          wall_seconds=process["wall_seconds"])

        normalized_decisions = [
            dict(index=d["index"], status=d["status"], reason=d["reason"],
                 dependency_witness=d["dependency_witness"])
            for d in result["decisions"]]
        return dict(mode=mode, variant=variant, repetition=repetition,
                    setup_wall_seconds=setup, apply_wall_seconds=wall,
                    finish_seconds=update["finish_nanos"] / 1_000_000_000,
                    identity_update_seconds=result["timings"]["identity_update_seconds"],
                    selected_checking_seconds=result["timings"]["checking_seconds"],
                    receipt_seconds=result["timings"]["persistence_seconds"],
                    producer_seconds=result["timings"]["producer_seconds"],
                    recomputed_sccs=update["recomputed_sccs"],
                    retained_graph_used=update["retained_graph_used"],
                    counts=result["counts"], export_sha256=result["export_sha256"],
                    index_sha256=hashlib.sha256(canonical(expected_index)).hexdigest(),
                    decisions_sha256=hashlib.sha256(canonical(normalized_decisions)).hexdigest(),
                    receipt_audit=receipt, full_rust_wall_seconds=full_log["wall_seconds"],
                    other_oracles=more_oracles)
    finally:
        session.close()


def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.workloads / "manifest.json").read_text())
    pins = json.loads((HERE / "pins.json").read_text())
    args.export_pins = pins["export_sha256"]
    if manifest.get("profile") == "std-hashmap-expanded-v1":
        expanded = json.loads((HERE / "delta-pins.json").read_text())
        args.export_pins = expanded["export_sha256"]
    for variant in ("baseline",) + VARIANTS:
        require(file_hash(manifest["variants"][variant]["path"]) ==
                args.export_pins[variant],
                "frozen original export does not match verified pin: " + variant)
    for name in ("leanchecker", "leanchecker-paranoid"):
        info = manifest["tools"][name]
        require(file_hash(info["path"]) == pins["lean_release_binaries_sha256"][name],
                "independent oracle binary differs from pinned Lean release")

    report = dict(schema="mathgraph.retained-scc.same-host-ab.v1",
                  source_sha=subprocess.check_output(
                      ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  profile=manifest.get("profile", "original-v1"),
                  comparison="same captured index binary; retained SCC versus complete finish",
                  pairing="alternate full/retained ordering by variant and repetition",
                  timed_boundary="warm producer+authentication+index+checker+durable persistence",
                  setup_excluded=True, order_controls=True, source_exact=True,
                  gates=[], pairs=[], results={}, complete=False)
    report["binary_hashes"] = {
        name: file_hash(path) for name, path in
        [("producer", args.producer), ("checker", args.checker),
         ("indexer", args.indexer), ("index_session", args.index_session),
         ("full_checker", args.full_checker)]}
    report["source_hashes"] = {
        name: file_hash(REPO / name) for name in (
            "src/identity.rs", "src/bin/index_session.rs",
            "experiments/incremental/producer_delta.py",
            "experiments/incremental/benchmark_retained_scc.py")}
    write(args.out / "partial.json", report)
    references = {}
    for variant in ("baseline",) + VARIANTS:
        reference, process = fresh_index(
            manifest["variants"][variant]["path"], args.indexer,
            args.out / "reference" / variant)
        require(process["returncode"] == 0 and not process["timed_out"],
                "fresh full identity failed: " + variant)
        references[variant] = reference

    oracle_tools = {name: Path(manifest["tools"][name]["path"])
                    for name in ("leanchecker", "leanchecker-paranoid")}
    rng = random.Random(20261017)
    for variant_number, variant in enumerate(VARIANTS):
        report["results"][variant] = []
        for repetition in range(args.repetitions):
            pairdir = args.out / "pairs" / variant / str(repetition)
            # Balanced alternation prevents a single mode from benefiting from
            # always following the other one in a warm host's file/page cache.
            modes = MODES if (variant_number + repetition) % 2 == 0 else MODES[::-1]
            samples = {}
            for mode in modes:
                samples[mode] = one_mode(
                    args, variant, repetition, mode, references[variant],
                    references["baseline"], pairdir, oracle_tools)
            full, retained = samples["full"], samples["retained"]
            for field in ("counts", "export_sha256", "index_sha256",
                          "decisions_sha256"):
                require(canonical(full[field]) == canonical(retained[field]),
                        "differential retained/full decision mismatch: " + field)
            report["results"][variant].extend(samples[m] for m in modes)
            report["pairs"].append(dict(variant=variant, repetition=repetition,
                    order=list(modes), full_seconds=full["apply_wall_seconds"],
                    retained_seconds=retained["apply_wall_seconds"],
                    full_finish_seconds=full["finish_seconds"],
                    retained_finish_seconds=retained["finish_seconds"],
                    full_setup_seconds=full["setup_wall_seconds"],
                    retained_setup_seconds=retained["setup_wall_seconds"],
                    recomputed_sccs=retained["recomputed_sccs"]))
            write(args.out / "partial.json", report)
        pairs = [p for p in report["pairs"] if p["variant"] == variant]
        overall = paired_economics([
            dict(apply_wall_seconds=p["retained_seconds"],
                 direct_wall_seconds=p["full_seconds"]) for p in pairs],
            seed=20261017 + variant_number)
        finish = paired_economics([
            dict(apply_wall_seconds=p["retained_finish_seconds"],
                 direct_wall_seconds=p["full_finish_seconds"]) for p in pairs],
            seed=20261027 + variant_number)
        report.setdefault("economics", {})[variant] = dict(
            complete_transaction=overall, native_scc_finish=finish,
            full_startup_median=statistics.median(p["full_setup_seconds"] for p in pairs),
            retained_startup_median=statistics.median(
                p["retained_setup_seconds"] for p in pairs),
            recomputed_sccs=[p["recomputed_sccs"] for p in pairs])
    require(all(file_hash(REPO / name) == expected
                for name, expected in report["source_hashes"].items()),
            "source bytes changed while measuring")
    require(all(file_hash(getattr(args, name)) == expected
                for name, expected in report["binary_hashes"].items()),
            "executable bytes changed while measuring")
    report["gates"].append(dict(name="all_mode_partitions_full_index_and_oracles", passed=True))
    report["gates"].append(dict(name="source_and_binary_identity_unchanged", passed=True))
    report["complete"] = True
    report["correctness_passed"] = True
    write(args.out / "summary.json", report)
    lines = ["# Same-host retained SCC vs full SCC index: independent A/B",
             "", "Correctness: PASS; exact full-index equality and all fresh verifier oracles.",
             "Five independent pairs per edit, alternating execution order. Timings exclude",
             "cold baseline seeding and module import. The same binary, producer, policy,",
             "HMAC issuer and selected checker are used for both modes.", "",
             "| Edit | Full-index warm s | Retained-index warm s | Saving | Pairs | Gate |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for v in VARIANTS:
        e = report["economics"][v]["complete_transaction"]
        f = report["economics"][v]["native_scc_finish"]
        lines.append("| " + v + " | " +
             f"{e['direct_median_wall_seconds']:.6f} | " +
             f"{e['apply_median_wall_seconds']:.6f} | " +
             f"{(1-e['median_ratio'])*100:.2f}% | " +
             f"{e['paired_wins']}/{e['paired_count']} | {e['status']} |")
        lines.append("")
        lines.append(v + " SCC-only finish: " +
                     f"{f['direct_median_wall_seconds']:.6f} s full vs " +
                     f"{f['apply_median_wall_seconds']:.6f} s retained; " +
                     f"{f['status']}. Recomputed SCCs: " +
                     str(report["economics"][v]["recomputed_sccs"]))
    lines += ["", "Comparison is not a proof of asymptotically change-proportional",
              "verification: complete-index serialization, materialization, hashing,",
              "selected-parser work and HMAC receipt creation are still O(total).",
              "A regression or NO_SPEEDUP is retained, never replaced by a phase-only win.", ""]
    (args.out / "summary.md").write_text("\n".join(lines))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workloads", "producer", "checker", "indexer",
                 "index_session", "full_checker", "authority_key", "out"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions != 5:
        parser.error("frozen qualification uses exactly five pairs per edit")
    for name in ("workloads", "producer", "checker", "indexer",
                 "index_session", "full_checker", "authority_key", "out"):
        setattr(args, name, getattr(args, name).resolve())
    if args.out.exists():
        parser.error("use a new output directory")
    require(len(args.authority_key.read_bytes()) == 32,
            "issuer key length invalid")
    try:
        report = run(args)
        print(json.dumps(dict(correctness=report["correctness_passed"],
                              economics=report["economics"]), sort_keys=True))
    except BaseException:
        if args.out.exists():
            (args.out / "failure.txt").write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
