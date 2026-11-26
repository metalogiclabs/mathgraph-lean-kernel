"""Independently join original and new raw artifacts by executable and input identity."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--directory", type=Path, required=True)
p.add_argument("--manifest", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
p.add_argument("--generic-only", action="store_true")
a = p.parse_args()
manifest = json.loads(a.manifest.read_text())
prescribed = {t["name"]: t for t in manifest["tests"] if t["outcome"] in ("accept", "reject")}
assert len(prescribed) == 240
GENERIC = "a76e2bbfe07ce80b204937548b7a00524bee1bff113fe19c9e1244ed93443f46"
original_sha = "6f55b2f7d754e4310589fe74aed040ae98ba82d39ba395bffd7cb6d439a0821e"
src = "de6696fcecbe99e6fcab5bb68c5974e1e9a04e49"
expected = {"cedar":151772,"con-leche":38246,"cslib":413186,"init":59979,"perf/magma-string-n4":3542,"perf/magma-string-pair-n9":3542,"reachability":4846,"std":103885,"navier-stokes-euler":129845}
archives, retained = [], {}
metadata = json.loads((a.directory / "artifact-metadata.json").read_text())

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_archive(name, known=None):
    path = a.directory / name
    digest = sha(path.read_bytes())
    if known:
        assert digest == known
    if name in metadata:
        assert digest == metadata[name]["digest"].removeprefix("sha256:")
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    archives.append({"name": name, "sha256": digest,
                     "file_digests": {n: sha(data) for n, data in files.items()},
                     "metadata": metadata.get(name)})
    for key, data in files.items():
        if key.endswith((".bin", ".zip", ".tsv", ".ndjson", ".so")):
            continue
        if name == "original.zip" and key not in {
            "portable/identity.json", "portable/rows.json", "portable/summary.json",
            "comparison/identity.json", "comparison/rows.json", "comparison/summary.json",
            "source-controls/rows.json", "source-controls/summary.json",
            "candidate-compiler.txt", "candidate-build-flags.txt", "candidate-source-tree.txt",
        }:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        retained[name + "/" + key] = {"sha256": sha(data), "utf8": text}
    return files

def js(files, name):
    return json.loads(files[name])

def verify_portable(files, prefix, binary_hash):
    identity = js(files, prefix + "/identity.json")
    assert identity["binary_sha256"] == binary_hash
    rows = js(files, prefix + "/rows.json")
    names = {r["name"] for r in rows}
    wanted = {name for name, t in prescribed.items() if t["size"] <= 10 * 1024**2}
    assert names == wanted and len(rows) == 230
    for row in rows:
        t = prescribed[row["name"]]
        code = 0 if t["outcome"] == "accept" else 1
        assert row["observed"] == row["expected"] == code and row["sha256"] == t["sha256"], row
    return {r["name"]: {"raw_exit": r["observed"], "input_sha256": r["sha256"],
                       "binary_sha256": binary_hash} for r in rows}

original = read_archive("original.zip", original_sha)
assert sha(original["builds/candidate.bin"]) == GENERIC
observations = verify_portable(original, "portable", GENERIC)
identity = js(original, "comparison/identity.json")
assert identity["candidate_source_tree"] == src and identity["binary_sha256"]["candidate"] == GENERIC
assert identity["input_sha256"] == prescribed["mathlib"]["sha256"]
full_rows = js(original, "comparison/rows.json")
assert len(full_rows) == 8
for row in full_rows:
    assert row["raw_exit"] == 0 and row["complete_count"]
    tag = f'{row["mode"]}-{row["arm"]}-{row["round"]}'
    assert re.search(rb"[Cc]hecked 739167 declarations\b", original["comparison/" + tag + ".stdout"])
observations["mathlib"] = {"raw_exit": 0, "input_sha256": prescribed["mathlib"]["sha256"],
                          "checked_declarations": 739167, "binary_sha256": GENERIC}
controls = js(original, "source-controls/rows.json")
assert len(controls) == 16 and all(r["observed"] == r["expected"] for r in controls)

for case, count in expected.items():
    name = "flash-inline-large-" + case.replace("perf/", "") + ".zip"
    files = read_archive(name)
    assert sha(files["original-inline-qualification.zip"]) == original_sha
    assert sha(files["candidate.bin"]) == GENERIC
    row = js(files, "verdict.json")
    inp = js(files, "input.json")
    t = prescribed[case]
    assert row["name"] == inp["name"] == case
    assert row["binary_sha256"] == GENERIC
    assert inp["size"] == t["size"] and inp["sha256"] == row["input_sha256"] == t["sha256"]
    assert row["raw_exit"] == 0 and row["checked_declarations"] == row["expected_declarations"] == count
    counts = re.findall(rb"[Cc]hecked (\d+) declarations", files["candidate.stdout"])
    assert counts and int(counts[-1]) == count
    assert case not in observations
    observations[case] = row
assert set(observations) == set(prescribed) and len(observations) == 240

if a.generic_only:
    result = {"state": "WARRANTED_BOUNDED_GENERIC_240", "generic_binary_sha256": GENERIC,
              "candidate_src_tree": src, "prescribed_correct": 240, "prescribed_total": 240,
              "prescribed_observations": observations, "source_controls_correct": len(controls),
              "archives": archives, "raw_text_entries": retained,
              "boundary": "Exact frozen generic executable only. Native-build comparison remains separate and UNKNOWN."}
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"state": result["state"], "generic_prescribed_correct": 240,
                      "archives_verified": len(archives), "retained_text_entries": len(retained)}))
    raise SystemExit(0)

native = read_archive("flash-inline-native-comparison.zip")
native_id = js(native, "comparison/identity.json")
native_hashes = {arm: sha(native[f"builds/{arm}.bin"]) for arm in ("baseline", "candidate")}
assert native_id["binary_sha256"] == native_hashes and native_id["candidate_source_tree"] == src
assert native_id["input"] == {"size": prescribed["mathlib"]["size"], "sha256": prescribed["mathlib"]["sha256"]}
native_portable = verify_portable(native, "portable", native_hashes["candidate"])
native_controls = js(native, "source-controls/rows.json")
assert len(native_controls) == 16 and all(r["observed"] == r["expected"] for r in native_controls)
rows = js(native, "comparison/rows.json")
assert len(rows) == 6 and {(r["pair"], r["arm"]) for r in rows} == {(n, arm) for n in range(3) for arm in ("baseline", "candidate")}
for row in rows:
    tag = f'{row["arm"]}-{row["pair"]}'
    assert row["raw_exit"] == 0 and row["checked_declarations"] == 739167
    assert re.search(rb"[Cc]hecked 739167 declarations\b", native[f"comparison/{tag}.stdout"])
    wall, user, system, rss = native[f"comparison/{tag}.time"].decode().splitlines()[-1].split("\t")
    assert row["wall_s"] == float(wall) and row["cpu_s"] == float(user) + float(system) and row["max_rss_kib"] == int(rss)
medians = {arm: {key: statistics.median(r[key] for r in rows if r["arm"] == arm)
                for key in ("cpu_s", "wall_s", "max_rss_kib")} for arm in native_hashes}
by_pair = {(r["pair"], r["arm"]): r for r in rows}
paired = [by_pair[n, "candidate"]["cpu_s"] / by_pair[n, "baseline"]["cpu_s"] for n in range(3)]
cpu_ratio = medians["candidate"]["cpu_s"] / medians["baseline"]["cpu_s"]
rss = {arm: max(r["max_rss_kib"] for r in rows if r["arm"] == arm) for arm in native_hashes}
rss_ratio = rss["candidate"] / rss["baseline"]
supported = native_hashes["baseline"] != native_hashes["candidate"] and cpu_ratio <= 0.99 and all(r < 1 for r in paired) and rss_ratio <= 1.05
summary = js(native, "comparison/summary.json")
assert summary["medians"] == medians and summary["paired_cpu_ratios"] == paired
assert summary["cpu_ratio"] == cpu_ratio and summary["peak_rss_ratio"] == rss_ratio and summary["gate_passed"] == supported
result = {"state": "WARRANTED_BOUNDED_GENERIC_240", "base_commit": native_id["base_commit"],
          "candidate_src_tree": src, "generic_binary_sha256": GENERIC,
          "prescribed_correct": len(observations), "prescribed_total": len(prescribed),
          "prescribed_observations": observations, "source_controls_correct": len(controls),
          "native": {"summary": summary, "binary_sha256": native_hashes, "portable_correct": len(native_portable),
                     "source_controls_correct": len(native_controls), "complete_mathlib_observations": len(rows)},
          "archives": archives, "raw_text_entries": retained,
          "lineage": {"generic_mathlib_run": 45723515088, "native_large_run": 45730741082,
                      "harness_commit": "0f862bf95ebce5f410295d81bde8118ff28981e8",
                      "submitted_release_commit": "bc704eebed4e009bc66af1a849f18315c11f1926",
                      "submitted_release_pr": "https://github.com/leanprover/lean-kernel-arena/pull/398",
                      "hardware_capability_probe": "https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711422359"},
          "boundary": "Generic frozen executable: 240 exact prescribed outcomes. Separate native build: 230 portable plus full Mathlib, 16 source controls, six CPU/RSS observations. Native nine-large qualification and hardware instructions remain UNKNOWN; no release or rank promotion."}
a.out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"state": result["state"], "generic_prescribed_correct": len(observations),
                  "native": summary, "archives_verified": len(archives), "retained_text_entries": len(retained)}, indent=2))
