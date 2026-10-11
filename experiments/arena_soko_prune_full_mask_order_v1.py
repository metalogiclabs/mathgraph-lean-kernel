#!/usr/bin/env python3
"""Full original Mathlib exact-byte diagnostic of pruning's semantic work.

Retains all checker judgments, measures only counts (not rank instructions).
The source-pinned binary emits one JSON census on each checker thread exit.
"""
import hashlib, json, os, pathlib, subprocess, sys, time

data=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
expected_len=6184415052
expected_sha="22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
assert data.is_file() and data.stat().st_size==expected_len,("BAD_MATHLIB_SIZE", data.stat().st_size)
h=hashlib.sha256()
with data.open("rb") as f:
    while b:=f.read(8*1024*1024): h.update(b)
assert h.hexdigest()==expected_sha,("WRONG_MATHLIB_SHA", h.hexdigest())
print("PRUNE_FULL_MATHLIB_FROZEN="+json.dumps({
    "bytes":expected_len,"sha256":expected_sha}),flush=True)

bins=["/tmp/prune-full-diagnostic.bin","--stdin","--nat-extension",
      "--string-extension","--axiom-allow-all","--threads","4"]
begin=time.monotonic()
with data.open("rb") as f:
    result=subprocess.run(bins,stdin=f,stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE,timeout=3600)
wall=time.monotonic()-begin
stderr=result.stderr.decode("utf-8",errors="replace")
(out/"diagnostic-stderr.log").write_text(stderr)
assert result.returncode==0,("FULL_MATHLIB_NOT_ACCEPTED",result.returncode,stderr[-2000:])
parts=[json.loads(line.split("MG_PRUNE_CENSUS_THREAD=",1)[1])
       for line in stderr.splitlines()
       if "MG_PRUNE_CENSUS_THREAD=" in line]
assert 1<=len(parts)<=4,("WRONG_THREAD_COUNT",len(parts),stderr[-2500:])
keys=[k for k in parts[0] if k not in ("schema","authority")]
c={}
for key in keys:
    if isinstance(parts[0][key],list):
        c[key]=[sum(p[key][i] for p in parts) for i in range(len(parts[0][key]))]
    else:
        c[key]=sum(p[key] for p in parts)
assert c["requests"]==sum(c[k] for k in
    ("mask_zero","from_nil","frame_covers","source_cell_hits",
     "direct_memo_hits","cold")),c
assert c["cold"]==sum(c["cold_mask_pop"]),c
assert c["source_cell_conflicts"] == (c["source_cache_supermask"] + c["source_cache_submask"] + c["source_cache_incomparable"]),c
assert c["requests"]==sum(c["all_mask_pop"]),c
assert c["cold"]>1000,("TOO_FEW_COLD_REQUESTS",c)
den=max(1,c["cold"])
groups={
    "cold_fraction_of_requests":c["cold"]/c["requests"],
    "cold_near_zero":c["cold_mask_pop"][0]/den,
    "cold_one_near":c["cold_mask_pop"][1]/den,
    "cold_two_near":c["cold_mask_pop"][2]/den,
    "cold_three_or_four_near":c["cold_mask_pop"][3]/den,
    "cold_more_than_four_near":sum(c["cold_mask_pop"][4:])/den,
    "cold_far":c["far_cold"]/den,
    "cold_source_cons":c["cold_from_cons"]/den,
    "cold_source_frame":c["cold_from_frame"]/den,
    "cell_hits_per_request":c["source_cell_hits"]/c["requests"],
    "conflicting_cell_masks_per_request":c["source_cell_conflicts"]/c["requests"],
    "cached_mask_is_supermask_conflict_fraction":c["source_cache_supermask"]/max(1,c["source_cell_conflicts"]),
    "cached_mask_is_submask_conflict_fraction":c["source_cache_submask"]/max(1,c["source_cell_conflicts"]),
    "cached_mask_is_incomparable_conflict_fraction":c["source_cache_incomparable"]/max(1,c["source_cell_conflicts"]),
    "direct_memo_hits_per_request":c["direct_memo_hits"]/c["requests"],
    "frame_covers_per_request":c["frame_covers"]/c["requests"],
    "avg_cons_processed_per_cold":c["nodes_cons"]/den,
    "avg_frame_processed_per_cold":c["nodes_frame"]/den,
    "avg_skipped_cons_per_cold":c["skipped_cons"]/den,
    "avg_slots_copied_per_cold":c["copied_slots"]/den,
    "frame_intern_hit_rate":c["frame_intern_hits"]/max(1,
         c["frame_intern_hits"]+c["frame_intern_new"]+
         c["frame_intern_hash_collisions"]),
    "frame_intern_collision_rate":c["frame_intern_hash_collisions"]/max(1,
         c["frame_intern_hits"]+c["frame_intern_new"]+
         c["frame_intern_hash_collisions"])
}
report={
    "warrant":"diagnostic-only, fully original pinned Mathlib, full ACCEPT",
    "report_type":"semantic work-count census, not PMU instruction timing",
    "source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
    "checker_basis":"qualified sparse reset + 4x growth + env singleprobe",
    "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
    "export_sha256":expected_sha,"export_bytes":expected_len,
    "run_commit":os.environ.get("GITHUB_SHA"),
    "accepted":True,"workers_with_census":len(parts),
    "wall_seconds_instrumented":wall,
    "thread_rows":parts,"total":c,"derived":groups,
    "official_rank_qualified":False
}
(out/"full-mathlib-prune-census.json").write_text(json.dumps(report,indent=2)+"\n")
print("PRUNE_FULL_MATHLIB_SUMMARY="+json.dumps({
   "accepted":True, "workers_with_census":len(parts),
   "wall_seconds_instrumented":wall,
   "cold_calls":c["cold"], "total_prune_requests":c["requests"],
   "source_cell_conflicts":c["source_cell_conflicts"],
   "mask_pop_histogram":c["cold_mask_pop"],
   "derived":groups,"official_rank_qualified":False}),flush=True)
