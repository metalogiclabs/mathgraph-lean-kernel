#!/usr/bin/env python3
"""Real pinned-Lean daemon checks; no mock producer or precomputed delta input."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOTS = ["IncrementalWorkload.early", "IncrementalWorkload.dependent",
         "IncrementalWorkload.dependent_spec", "Std.HashMap.getElem?_insert",
         "Std.HashMap.getElem?_erase", "IncrementalWorkload.unrelated",
         "IncrementalWorkload.leaf", "IncrementalWorkload.typed",
         "IncrementalWorkload.typed_identity"]
PATHS = ["IncrementalWorkload/Base.lean", "IncrementalWorkload/Derived.lean",
         "IncrementalWorkload/Leaves.lean", "Workload.lean"]
BASE_SHA = "d81ecde8f818ed8d8748b476e22412ec74820a49edbe7986c2c3633a3d66bef0"
EARLY_SHA = "13323bf721599b9b77fe0ea94da5c4632edd2a25188842fb09738bfdf74fdd9f"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_runtime_environment(workload):
    """Launch Lean helpers from the exact release without a default elan toolchain."""
    here = Path(__file__).resolve().parent
    pins = json.loads((here / "pins.json").read_text())
    manifest = workload.parents[1] / "manifest.json"
    if manifest.is_file():
        lean = Path(json.loads(manifest.read_text())["tools"]["lean"]["path"]).resolve()
    else:
        prefix = subprocess.check_output([os.environ.get("ELAN", "elan"), "run",
            pins["lean_toolchain"], "lean", "--print-prefix"], text=True).strip()
        lean = Path(prefix).resolve() / "bin" / "lean"
    if sha(lean) != pins["lean_release_binaries_sha256"]["lean"]:
        raise ValueError("producer test Lean runtime differs from exact release pin")
    env = dict(os.environ, LEAN_SYSROOT=str(lean.parent.parent), LEAN_PATH="",
               PATH=str(lean.parent) + os.pathsep + os.environ.get("PATH", ""))
    revision = subprocess.check_output([str(lean), "--githash"], env=env, text=True).strip()
    if revision != pins["lean_githash"]:
        raise ValueError("producer test Lean revision differs from exact release pin")
    return env, dict(path=str(lean), sha256=sha(lean), githash=revision,
                     toolchain=pins["lean_toolchain"])


def run(binary, workload, output, profile="original-v1"):
    producer_env, runtime = pinned_runtime_environment(workload)
    roots, baseline_sha, early_sha, delta_bytes = ROOTS, BASE_SHA, EARLY_SHA, 271
    if profile == "std-hashmap-expanded-v1":
        here = Path(__file__).resolve().parent
        pins = json.loads((here / "delta-pins.json").read_text())
        roots = json.loads((here / pins["roots_file"]).read_text())
        assert sha(here / pins["roots_file"]) == pins["roots_sha256"]
        baseline_sha, early_sha = (pins["export_sha256"][name]
                                  for name in ("baseline", "early-definition"))
        delta_bytes = 280
    files = {name: (workload / name).read_text() for name in PATHS}
    output.mkdir(parents=True, exist_ok=True)
    init_path = output / "init.json"
    baseline = output / "baseline.ndjson"
    init_path.write_text(json.dumps({"profile": profile, "source_files": files, "roots": roots,
                                     "baseline_export": str(baseline)}))
    start = time.monotonic()
    with open(output / "daemon.stderr", "w") as err:
        proc = subprocess.Popen([str(binary), str(init_path)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1,
                                env=producer_env)
        def receive():
            line = proc.stdout.readline()
            assert line, f"daemon exited: {proc.poll()}"
            return json.loads(line)
        def send(request):
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            return receive()
        try:
            ready = receive()
            assert ready["status"] == "ready", ready
            assert sha(baseline) == baseline_sha
            assert ready["profile"] == profile and ready["roots"] == roots
            cold_wall = time.monotonic() - start
            early = copy.deepcopy(files)
            early[PATHS[0]] = early[PATHS[0]].replace("early : Nat := 17", "early : Nat := 23")
            receipts = []
            for i in range(3):
                path = output / f"delta-{i}.ndjson"
                receipt = send({"source_files": early, "delta_path": str(path),
                                "expected_changed_names": [ROOTS[0]]})
                assert receipt["status"] == "delta", receipt
                assert receipt["changed_names"] == [ROOTS[0]]
                assert receipt["stats"]["compared_local_constants"] == 7
                assert receipt["stats"]["imported_identity_retained"] is True
                assert receipt["stats"]["new_exprs"] == 4
                assert path.stat().st_size == delta_bytes
                receipts.append(receipt)
            assert len({sha(output / f"delta-{i}.ndjson") for i in range(3)}) == 1
            path = output / "fresh.ndjson"
            fresh = send({"op": "fresh", "source_files": early, "export_path": str(path)})
            assert fresh["status"] == "fresh", fresh
            assert sha(path) == early_sha
            no_op = output / "no-op.ndjson"
            receipt = send({"source_files": files, "delta_path": str(no_op),
                            "expected_changed_names": []})
            assert receipt["status"] == "delta", receipt
            assert no_op.stat().st_size == 0
            assert receipt["changed_names"] == []

            # Every file body is processed; an edit outside the announced region is caught.
            outside = copy.deepcopy(early)
            outside[PATHS[2]] = outside[PATHS[2]].replace("n * n + 3", "n * n + 4")
            def reject(source, expected, label):
                target = output / f"rejected-{label}.ndjson"
                receipt = send({"source_files": source, "delta_path": str(target),
                                "expected_changed_names": expected})
                assert receipt["status"] == "error", (label, receipt)
                assert not target.exists(), label
                return receipt
            controls = {"outside_hint": reject(outside, [ROOTS[0]], "outside-hint")}
            duplicate = reject(outside, [ROOTS[0], ROOTS[0]], "duplicate-hint")
            controls["duplicate_hint"] = duplicate
            both = send({"source_files": outside, "delta_path": str(output / "two.ndjson"),
                         "expected_changed_names": [ROOTS[0], "IncrementalWorkload.unrelated"]})
            assert both["status"] == "delta", both
            assert set(both["changed_names"]) == {ROOTS[0], "IncrementalWorkload.unrelated"}
            bad_import = copy.deepcopy(files)
            bad_import[PATHS[0]] = bad_import[PATHS[0]].replace("Std.Data.HashMap", "Std.Data.HashSet")
            controls["import_drift"] = reject(bad_import, [], "import")
            extra = copy.deepcopy(files)
            extra[PATHS[3]] += "\ndef ignoredChange : Nat := 42\n"
            controls["ignored_workload_command"] = reject(extra, [], "workload")
            add = copy.deepcopy(files)
            add[PATHS[0]] += "\ndef extraDeclaration : Nat := 1\n"
            controls["local_addition"] = reject(add, [], "addition")
            delete = copy.deepcopy(files)
            delete[PATHS[2]] = delete[PATHS[2]].replace("theorem leaf (n : Nat) : n = n := Eq.refl n", "")
            controls["local_deletion"] = reject(delete, [], "deletion")
            kind = copy.deepcopy(files)
            kind[PATHS[0]] = kind[PATHS[0]].replace("def early : Nat := 17", "axiom early : Nat")
            controls["kind_drift"] = reject(kind, [ROOTS[0]], "kind")
            proc.stdin.close()
            assert proc.wait(timeout=15) == 0
            report = {"schema": "mathgraph.delta-producer-probe.v1", "profile": profile, "ready": ready,
                      "runtime": runtime,
                      "cold_wall_seconds": cold_wall, "delta_receipts": receipts,
                      "fresh": fresh, "negative_controls": controls,
                      "baseline_sha256": sha(baseline), "fresh_sha256": sha(path),
                      "delta_bytes": delta_bytes, "baseline_bytes": baseline.stat().st_size}
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            return report
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--workload", type=Path, default=Path(__file__).parent / "workload")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=("original-v1", "std-hashmap-expanded-v1"), default="original-v1")
    args = parser.parse_args()
    if args.output:
        report = run(args.binary.resolve(), args.workload.resolve(), args.output.resolve(), args.profile)
    else:
        with tempfile.TemporaryDirectory(prefix="delta-producer-") as tmp:
            report = run(args.binary.resolve(), args.workload.resolve(), Path(tmp), args.profile)
    print(json.dumps({"status": "passed", "baseline_sha256": report["baseline_sha256"],
                      "fresh_sha256": report["fresh_sha256"], "delta_bytes": report["delta_bytes"],
                      "negative_controls": len(report["negative_controls"])}))

if __name__ == "__main__":
    main()
