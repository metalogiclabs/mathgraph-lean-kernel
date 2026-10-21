#!/usr/bin/env python3
"""Real Lean predecessor revisions, exporter history, and fail-stop recovery."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import select
import subprocess

from test_delta_producer import PATHS, ROOTS, pinned_runtime_environment


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Producer:
    def __init__(self, binary, workload, output, files, *, chain=True, profile="original-v1"):
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        roots = ROOTS
        if profile == "std-hashmap-expanded-v1":
            here = Path(__file__).resolve().parent
            pins = json.loads((here / "delta-pins.json").read_text())
            roots = json.loads((here / pins["roots_file"]).read_text())
        initial = dict(source_files=files, profile=profile, roots=roots,
                       baseline_export=str(output / "baseline.ndjson"))
        if chain is not None:
            initial["revision_chain"] = chain
        init = output / "init.json"
        init.write_text(json.dumps(initial))
        env, self.runtime = pinned_runtime_environment(workload)
        self.stderr = (output / "stderr.log").open("wb")
        self.process = subprocess.Popen([str(binary), str(init)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr,
                                        env=env)
        self.ready = self.receive()
        assert self.ready["status"] == "ready", self.ready
        baseline = output / "baseline.ndjson"
        self.baseline_sha256 = digest(baseline)
        # The producer has already admitted the export into its owned state.
        # Retain the content hash and small source/delta witnesses, avoiding
        # redundant full exports for every short-lived control process.
        baseline.unlink()

    def receive(self):
        assert select.select([self.process.stdout], [], [], 120)[0], "producer timeout"
        line = self.process.stdout.readline()
        assert line, f"producer exited: {self.process.poll()}"
        return json.loads(line)

    def request(self, request):
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        self.process.stdin.flush()
        return self.receive()

    def delta(self, sources, expected, label):
        path = self.output / (label + ".ndjson")
        result = self.request(dict(source_files=sources, delta_path=str(path),
                                   expected_changed_names=expected))
        assert result["status"] == "delta", (label, result)
        assert sorted(result["changed_names"]) == sorted(expected), (label, result)
        assert result["stats"]["compared_local_constants"] == 7, result
        assert result["stats"]["imported_identity_retained"] is True, result
        return result, path

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdout.close()
        self.stderr.close()


def run(binary, workload, output, profile):
    files = {name: (workload / name).read_text() for name in PATHS}
    early = copy.deepcopy(files)
    early[PATHS[0]] = early[PATHS[0]].replace("early : Nat := 17", "early : Nat := 23")
    both = copy.deepcopy(early)
    both[PATHS[2]] = both[PATHS[2]].replace("n * n + 3", "n * n + 5")
    unrelated = copy.deepcopy(both)
    unrelated[PATHS[0]] = files[PATHS[0]]
    assert early != files and both != early and unrelated != both
    steps = [("early", early, [ROOTS[0]]),
             ("cumulative", both, ["IncrementalWorkload.unrelated"]),
             ("restore-early", unrelated, [ROOTS[0]]),
             ("restore-all", files, ["IncrementalWorkload.unrelated"]),
             ("unchanged", files, []),
             ("revisit-early", early, [ROOTS[0]])]
    runs = []
    for label in ("warm", "cold-replay"):
        producer = Producer(binary, workload, output / label, files, profile=profile)
        observations = []
        try:
            assert producer.ready["revision"] == 0, producer.ready
            for name, sources, expected in steps:
                result, path = producer.delta(sources, expected, name)
                assert result["revision"] == len(observations) + 1, result
                observations.append(dict(label=name, result=result, delta_sha256=digest(path),
                                         delta_bytes=path.stat().st_size))
            # Exporter history is retained: revisiting the earlier term needs
            # its replacement declaration, while all expression DAG rows exist.
            assert observations[-1]["result"]["stats"]["new_exprs"] == 0, observations[-1]
            assert observations[4]["delta_bytes"] == 0, observations[4]
            assert observations[2]["result"]["stats"]["new_exprs"] == 0, observations[2]
            assert observations[3]["result"]["stats"]["new_exprs"] == 0, observations[3]
            # A full fresh export is an observation, not a chain commit.
            fresh = producer.request(dict(op="fresh", source_files=files,
                                          export_path=str(producer.output / "fresh.ndjson")))
            assert fresh["status"] == "fresh", fresh
            assert digest(producer.output / "fresh.ndjson") == producer.baseline_sha256
            (producer.output / "fresh.ndjson").unlink()
            result, path = producer.delta(early, [], "after-fresh-unchanged")
            assert path.stat().st_size == 0, result
            assert result["revision"] == len(steps) + 1, result
            runs.append(dict(ready=producer.ready, baseline_sha256=producer.baseline_sha256,
                             observations=observations))
        finally:
            producer.close()
    assert [r["delta_sha256"] for r in runs[0]["observations"]] == [
        r["delta_sha256"] for r in runs[1]["observations"]], "cold source replay changed DAG history"

    # A false hint poisons the chain; the process cannot continue from partial
    # state. A new process can deterministically reconstruct accepted updates.
    producer = Producer(binary, workload, output / "poison", files, profile=profile)
    try:
        producer.delta(early, [ROOTS[0]], "accepted")
        result = producer.request(dict(source_files=both,
                                       delta_path=str(producer.output / "bad.ndjson"),
                                       expected_changed_names=[]))
        assert result["status"] == "error", result
        try:
            code = producer.process.wait(timeout=15)
        except subprocess.TimeoutExpired as error:
            raise AssertionError("chain producer survived a rejected source revision") from error
        assert code != 0, code
    finally:
        producer.close()

    # Legacy absent and explicit false init preserve repeated genesis-relative
    # deltas and the old exact response field set.
    for flag in (None, False):
        producer = Producer(binary, workload, output / ("legacy-absent" if flag is None else "legacy-false"),
                            files, chain=flag, profile=profile)
        try:
            assert "revision" not in producer.ready, producer.ready
            first, first_path = producer.delta(early, [ROOTS[0]], "first")
            second, second_path = producer.delta(early, [ROOTS[0]], "second")
            assert digest(first_path) == digest(second_path)
            assert set(first) == set(second) == {
                "status", "delta_path", "changed_names", "local_names", "stats", "timings_ns"}
        finally:
            producer.close()
    report = dict(status="passed", profile=profile, runs=runs)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="original-v1",
                        choices=("original-v1", "std-hashmap-expanded-v1"))
    args = parser.parse_args()
    run(args.binary.resolve(), args.workload.resolve(), args.output.resolve(), args.profile)
    print(json.dumps(dict(status="passed", profile=args.profile)))


if __name__ == "__main__":
    main()
