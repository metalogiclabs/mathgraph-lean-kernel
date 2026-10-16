#!/usr/bin/env python3
"""Build the opt-in genuine Std export profile with the source-owned Lean producer."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from process import sha256

HERE = Path(__file__).resolve().parent
PROFILE = "std-hashmap-expanded-v1"
VARIANTS = ("baseline", "early-definition", "unrelated-definition", "theorem-leaf", "type-change")
SOURCES = ("Workload.lean", "IncrementalWorkload/Base.lean", "IncrementalWorkload/Derived.lean",
           "IncrementalWorkload/Leaves.lean")
COPY_FILES = SOURCES + ("lakefile.toml", "lean-toolchain")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def counts(path):
    records = Counter()
    decls = 0
    for line in path.open():
        row = json.loads(line)
        for key in ("inductive", "def", "thm", "opaque", "axiom", "quot"):
            if key not in row:
                continue
            records[key] += 1
            if key == "inductive":
                decls += sum(len(row[key][part]) for part in ("types", "ctors", "recs"))
            else:
                decls += 1
    return dict(record_counts=dict(records), declaration_records=sum(records.values()),
                declaration_count=decls)


def build(args):
    original = args.workloads.resolve()
    out = args.out.resolve()
    producer = args.producer.resolve()
    if out.exists():
        raise ValueError("use a new expanded workload directory")
    pin = json.loads((HERE / "delta-pins.json").read_text())
    roots_path = HERE / pin["roots_file"]
    if pin["profile"] != PROFILE or sha256(roots_path) != pin["roots_sha256"]:
        raise ValueError("expanded root policy differs from its pin")
    roots = json.loads(roots_path.read_text())
    if len(roots) != pin["root_count"] or set(pin["export_sha256"]) != set(VARIANTS):
        raise ValueError("expanded profile pins are incomplete")
    old = json.loads((original / "manifest.json").read_text())
    if old["toolchain"] != pin["lean_toolchain"]:
        raise ValueError("original workload toolchain differs")
    if old.get("profile"):
        raise ValueError("--workloads must be the unchanged original qualification workload")
    for variant in VARIANTS:
        if sha256(old["variants"][variant]["path"]) != old["variants"][variant]["sha256"]:
            raise ValueError("original workload export changed: " + variant)
        source_dir = original / variant / "source"
        for name in COPY_FILES:
            target = out / variant / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_dir / name, target)
    manifest = dict(schema="mathgraph.producer-delta-workloads.v1", profile=PROFILE,
                    toolchain=pin["lean_toolchain"], roots=roots, roots_sha256=sha256(roots_path),
                    roots_file=str(roots_path), tools=old["tools"], variants={},
                    original_manifest=str(original / "manifest.json"),
                    original_manifest_sha256=sha256(original / "manifest.json"),
                    producer=dict(path=str(producer), sha256=sha256(producer),
                                  source_mode="fixed-three-bodies-over-persistent-Std-import"))
    source_files = lambda variant: {name: (out / variant / "source" / name).read_text()
                                    for name in SOURCES}
    baseline_path = out / "baseline" / "export.ndjson"
    init = dict(profile=PROFILE, source_files=source_files("baseline"), roots=roots,
                baseline_export=str(baseline_path))
    init_path = out / "producer-init.json"
    write(init_path, init)
    lean_dir = str(Path(old["tools"]["lean"]["path"]).parent)
    env = dict(os.environ, PATH=lean_dir + os.pathsep + os.environ.get("PATH", ""))
    command = [str(producer), str(init_path)]
    with (out / "producer.stderr").open("w") as err:
        started = time.perf_counter()
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, env=env, text=True, bufsize=1)
        def receive():
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("producer exited unexpectedly; see producer.stderr")
            response = json.loads(line)
            if response.get("status") == "error":
                raise RuntimeError(response.get("error", "producer error"))
            return response
        try:
            ready = receive()
            cold_wall = time.perf_counter() - started
            if ready["status"] != "ready" or ready["profile"] != PROFILE or ready["roots"] != roots:
                raise ValueError("producer accepted a different profile or roots")
            if ready["stats"]["exported_constants"] != pin["declaration_count"]:
                raise ValueError("producer exported unexpected declaration count")
            write(out / "producer-ready.json", ready)
            for variant in VARIANTS:
                path = out / variant / "export.ndjson"
                if variant == "baseline":
                    receipt = ready
                    wall = cold_wall
                else:
                    request = dict(op="fresh", source_files=source_files(variant), export_path=str(path))
                    write(out / variant / "producer-request.json", request)
                    start = time.perf_counter()
                    proc.stdin.write(json.dumps(request) + "\n")
                    proc.stdin.flush()
                    receipt = receive()
                    wall = time.perf_counter() - start
                    if receipt["status"] != "fresh":
                        raise ValueError("producer did not return a fresh oracle export")
                write(out / variant / "producer-receipt.json", receipt)
                digest = sha256(path)
                if digest != pin["export_sha256"][variant]:
                    raise ValueError("expanded export differs from genuine .olean pin: " + variant)
                info = dict(path=str(path), sha256=digest, bytes=path.stat().st_size,
                            **counts(path), source_sha256={name: sha256(out / variant / "source" / name)
                                                          for name in COPY_FILES},
                            original_build=old["variants"][variant].get("build"),
                            build=dict(mode="source-owned Lean elaboration; no .olean rebuild needed",
                                       returncode=0, wall_seconds=receipt["timings_ns"]["elaboration"] / 1e9),
                            export_process=dict(command=command, cwd=None, returncode=0,
                                                wall_seconds=wall, producer_receipt=receipt,
                                                cold_initialization=(variant == "baseline")))
                if info["declaration_count"] != pin["declaration_count"]:
                    raise ValueError("unexpected declaration count: " + variant)
                manifest["variants"][variant] = info
                write(out / "manifest.json", manifest)
                print(json.dumps(dict(variant=variant, bytes=info["bytes"], sha256=digest)), flush=True)
            proc.stdin.close()
            if proc.wait(timeout=30):
                raise RuntimeError("producer did not exit cleanly")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workloads", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--producer", "--producer-binary", dest="producer", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args)
    print(json.dumps(dict(status="ready", profile=manifest["profile"],
                          manifest=str(args.out.resolve() / "manifest.json"))))

if __name__ == "__main__":
    main()
