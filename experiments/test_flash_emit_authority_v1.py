#!/usr/bin/env python3
import json, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
script=ROOT/"experiments/flash_emit_authority_v1.py"

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    s=td/"semantic.json"
    subprocess.run([
        "python3",str(script),
        "--kind","semantic_authority",
        "--id","s1","--family","x","--capability-id","c1","--run","1",
        "--implementation-identity","tree:abc",
        "--semantic-scope","409_current_arena_exports","--semantic-pass",
        "--out",str(s)
    ],check=True)
    x=json.loads(s.read_text())
    assert x["semantic_pass"] is True
    assert x["semantic_scope"]=="409_current_arena_exports"

    obs=td/"obs.json"; obs.write_text('{"mathlib_speedup":1.04}\n')
    p=td/"perf.json"
    subprocess.run([
        "python3",str(script),
        "--kind","performance_authority",
        "--id","p1","--family","x","--capability-id","c1","--run","2",
        "--implementation-identity","tree:abc",
        "--performance-pass","--observations-json",str(obs),
        "--out",str(p)
    ],check=True)
    y=json.loads(p.read_text())
    assert y["performance_pass"] is True
    assert y["observations"]["mathlib_speedup"]==1.04

print("FLASH_AUTHORITY_EVENT_EMIT_TESTS_PASS")
