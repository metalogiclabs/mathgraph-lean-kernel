#!/usr/bin/env python3
"""Summarize exact expensive contextual-cache overlap after full Mathlib ACCEPT.

Observations are diagnostic counters. They are neither measured instruction
savings nor an independent semantic proof. Keep the full native export hash.
"""
import json,pathlib,sys
stderr=pathlib.Path(sys.argv[1])
result=pathlib.Path(sys.argv[2])
raw=stderr.read_text(errors="replace")
prefix="FLASH_JUDGMENT_CENSUS="
workers=[]
for line in raw.splitlines():
    if prefix in line:
        value=line.split(prefix,1)[1].strip()
        workers.append(json.loads(value))
assert workers,("NO_WORKER_COUNTERS",raw[-5000:])
fields=tuple(workers[0])
assert all(set(w)==set(fields) for w in workers)
total={key:sum(w[key] for w in workers) for key in fields}
assert total["type_calls"] > 1000 and total["eval_calls"] > 1000,total
assert total["type_hits"]<=total["type_calls"]
assert total["eval_hits"]<=total["eval_calls"]
assert total["eval_with_checked_type"]<=total["eval_with_type"]<=total["eval_calls"]
assert total["type_miss_with_value"]<=total["type_with_value"]<=total["type_calls"]
assert total["eval_miss_with_type"]<=total["eval_with_type"]
rates={
  "type_cached_hit_fraction":total["type_hits"]/total["type_calls"],
  "eval_cached_hit_fraction":total["eval_hits"]/total["eval_calls"],
  "type_requested_after_value_fraction":total["type_with_value"]/total["type_calls"],
  "eval_requested_after_type_fraction":total["eval_with_type"]/total["eval_calls"],
  "eval_requested_after_checked_type_fraction":total["eval_with_checked_type"]/total["eval_calls"],
  "type_miss_with_existing_value_fraction":total["type_miss_with_value"]/total["type_calls"],
  "eval_miss_with_existing_type_fraction":total["eval_miss_with_type"]/total["eval_calls"],
}
report={
 "scope":"Source-pinned complete Mathlib, 4 worker threads, open composite expression keys",
 "metric":"post-key_env contextual cache hits and cross-domain occupancy; not proof of saved work",
 "independent_full_mathlib_accepted":True,
 "diagnostic_build":True,
 "separate_authority":"presence of a value does not confer type-checking warrant",
 "worker_records":workers,
 "aggregate":total,
 "rates":rates,
}
result.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_VNEXT_FULL_MATHLIB_CENSUS="+json.dumps({"n_workers":len(workers),"totals":total,"rates":rates}),flush=True)
