#!/usr/bin/env python3
"""Diagnostic-only census of proof checker environment pruning.

Pins Sokonanoda source AFTER existing qualified sparse pruning, 4x PtrMap
growth and optional env-extend insertion; does not modify judgments or
cached values. Reports one JSON record per checker thread at thread exit.
Not a performance patch or rank claim.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/checker/eval/environment.rs"
s = p.read_text()
assert "self.tc_cache.prune_dm.at(slot)" in s, "Expected sparse reset source"
assert "self.tc_cache.prune_dm.put(slot, Id::of(e), mask, r);" in s
assert s.count("    fn prune_env(") == 1
assert s.count("    fn prune_env_cold(") == 1
assert s.count("    fn intern_frame(") == 1

marker = "impl<'t> TypeChecker<'_, 't, '_> {"
assert s.count(marker) == 1
reporter = r'''
// Diagnostic-only counters: neither a proof rule nor an optimization.
// A checker thread exits only after verification; TLS Drop emits its census.
// The top-level checker runs worker threads even for single-thread mode.
#[derive(Default)]
struct PruneCausalCensus {
    requests: u64,
    mask_zero: u64,
    from_nil: u64,
    frame_covers: u64,
    source_cell_hits: u64,
    source_cell_conflicts: u64,
    direct_memo_hits: u64,
    cold: u64,
    far_requests: u64,
    far_cold: u64,
    all_mask_pop: [u64; 8],
    cold_mask_pop: [u64; 8],
    cold_from_cons: u64,
    cold_from_frame: u64,
    cold_lsub: u64,
    nodes_cons: u64,
    nodes_frame: u64,
    skipped_cons: u64,
    copied_slots: u64,
    frame_intern_hits: u64,
    frame_intern_new: u64,
    frame_intern_hash_collisions: u64,
}

fn prune_population_bucket(mask: u64) -> usize {
    let n = (mask & !value::FAR).count_ones();
    match n {
        0 => 0,
        1 => 1,
        2 => 2,
        3..=4 => 3,
        5..=8 => 4,
        9..=16 => 5,
        17..=32 => 6,
        _ => 7,
    }
}

impl Drop for PruneCausalCensus {
    fn drop(&mut self) {
        if self.requests == 0 {
            return;
        }
        eprintln!("MG_PRUNE_CENSUS_THREAD={}", serde_json::json!({
            "schema": 1,
            "authority": "source-exact instrumented diagnostic, not Arena scoring",
            "requests": self.requests,
            "mask_zero": self.mask_zero,
            "from_nil": self.from_nil,
            "frame_covers": self.frame_covers,
            "source_cell_hits": self.source_cell_hits,
            "source_cell_conflicts": self.source_cell_conflicts,
            "direct_memo_hits": self.direct_memo_hits,
            "cold": self.cold,
            "far_requests": self.far_requests,
            "far_cold": self.far_cold,
            "all_mask_pop": self.all_mask_pop,
            "cold_mask_pop": self.cold_mask_pop,
            "cold_from_cons": self.cold_from_cons,
            "cold_from_frame": self.cold_from_frame,
            "cold_lsub": self.cold_lsub,
            "nodes_cons": self.nodes_cons,
            "nodes_frame": self.nodes_frame,
            "skipped_cons": self.skipped_cons,
            "copied_slots": self.copied_slots,
            "frame_intern_hits": self.frame_intern_hits,
            "frame_intern_new": self.frame_intern_new,
            "frame_intern_hash_collisions": self.frame_intern_hash_collisions
        }));
    }
}

std::thread_local! {
    static MG_PRUNE_CENSUS: std::cell::RefCell<PruneCausalCensus> =
        std::cell::RefCell::new(PruneCausalCensus::default());
}

#[inline(always)]
fn count_prune(f: impl FnOnce(&mut PruneCausalCensus)) {
    MG_PRUNE_CENSUS.with(|cell| {
        let mut row = cell.borrow_mut();
        f(&mut row);
    });
}

'''
s=s.replace(marker, reporter + marker)

# Pruning method controls, left exactly the same in their decisions.
start=s.index("    fn prune_env(")
end=s.index("    #[inline(never)]\n    fn prune_env_cold(",start)
a=s[start:end]
old="    fn prune_env(&mut self, e: E<'t>, mask: u64) -> E<'t> {\n"
assert a.count(old)==1
a=a.replace(old,old+"""        count_prune(|c| {
            c.requests += 1;
            c.all_mask_pop[prune_population_bucket(mask)] += 1;
            if (mask & value::FAR) != 0 {
                c.far_requests += 1;
            }
        });
""")
assert a.count("        if mask == 0 {\n            return self.lsub_base(e.lsub());")==1
a=a.replace("        if mask == 0 {\n            return self.lsub_base(e.lsub());",
            "        if mask == 0 {\n            count_prune(|c| c.mask_zero += 1);\n            return self.lsub_base(e.lsub());")
assert a.count("value::Env::Nil { .. } => return e,")==1
a=a.replace("value::Env::Nil { .. } => return e,",
            "value::Env::Nil { .. } => { count_prune(|c| c.from_nil += 1); return e; },")
assert a.count("if *m & mask == *m {\n                    return e;")==1
a=a.replace("if *m & mask == *m {\n                    return e;",
            "if *m & mask == *m {\n                    count_prune(|c| c.frame_covers += 1);\n                    return e;")
assert a.count("                let (m, r) = prune.get();")==2
a=a.replace("                let (m, r) = prune.get();",
            "                let (m, r) = prune.get();\n                if r.is_some() && m != mask { count_prune(|c| c.source_cell_conflicts += 1); }")
same="""                {
                    return r;
                }"""
assert a.count(same)==2,a.count(same)
a=a.replace(same,"""                {
                    count_prune(|c| c.source_cell_hits += 1);
                    return r;
                }""")
assert a.count("            return hit;")==1
a=a.replace("            return hit;", "            count_prune(|c| c.direct_memo_hits += 1);\n            return hit;")
assert a.count("        self.prune_env_cold(e, mask, slot)")==1
a=a.replace("        self.prune_env_cold(e, mask, slot)",
"""        count_prune(|c| {
            c.cold += 1;
            c.cold_mask_pop[prune_population_bucket(mask)] += 1;
            if (mask & value::FAR) != 0 { c.far_cold += 1; }
            if e.lsub().is_some() { c.cold_lsub += 1; }
            match e {
                value::Env::Cons { .. } => c.cold_from_cons += 1,
                value::Env::Framed { .. } => c.cold_from_frame += 1,
                value::Env::Nil { .. } => {}
            }
        });
        self.prune_env_cold(e, mask, slot)""")
s=s[:start]+a+s[end:]

# Expensive cold traversal: accumulate local counts, and only then update TLS.
start=s.index("    fn prune_env_cold(")
end=s.index("    #[inline(always)]\n    pub(crate) fn key_env(",start)
a=s[start:end]
one="""        let mut consumed = 0u32;
        let mut cur = e;"""
assert a.count(one)==1
a=a.replace(one,"""        let mut consumed = 0u32;
        let mut traced_cons = 0u64;
        let mut traced_frame = 0u64;
        let mut traced_skip = 0u64;
        let mut cur = e;""")
old="""                value::Env::Framed {
                    mask: fmask,"""
assert a.count(old)==1
a=a.replace(old,"""                value::Env::Framed {
                    mask: fmask,""") # increment only after opening branch
needle="""                } => {
                    let cut = u32::from(*cut);"""
assert a.count(needle)==1
a=a.replace(needle,"""                } => {
                    traced_frame += 1;
                    let cut = u32::from(*cut);""")
old="""                value::Env::Cons { v, parent, .. } => {
                    if rem & 1 != 0 {"""
assert a.count(old)==1
a=a.replace(old,"""                value::Env::Cons { v, parent, .. } => {
                    traced_cons += 1;
                    if rem & 1 != 0 {""")
old="""                    rem >>= hops;
                    consumed += hops;"""
assert a.count(old)==1
a=a.replace(old,"""                    traced_skip += u64::from(hops);
                    rem >>= hops;
                    consumed += hops;""")
old="""        let r = self.intern_frame(slots_hash, out_mask, slots, value::NEAR, rest, lsub);"""
assert a.count(old)==1
a=a.replace(old,"""        count_prune(|c| {
            c.nodes_cons += traced_cons;
            c.nodes_frame += traced_frame;
            c.skipped_cons += traced_skip;
            c.copied_slots += n as u64;
        });
        let r = self.intern_frame(slots_hash, out_mask, slots, value::NEAR, rest, lsub);""")
s=s[:start]+a+s[end:]

# Frame hash-cons outcomes: record whenever expensive reconstruction allocates,
# including hash collisions that are not safe to silently treat as identical.
start=s.index("    fn intern_frame(")
end=s.index("    fn frame_without(",start)
a=s[start:end]
old="""        {
            return e;
        }
        let e: E<'t> = self.arena.alloc(value::Env::Framed {"""
assert a.count(old)==1
a=a.replace(old,"""        {
            count_prune(|c| c.frame_intern_hits += 1);
            return e;
        }
        let e: E<'t> = self.arena.alloc(value::Env::Framed {""")
old="""        if let Err(vacant) = found {
            self.tc_cache.frames.insert_at(vacant, hash, e);
        }"""
assert a.count(old)==1
a=a.replace(old,"""        if let Err(vacant) = found {
            count_prune(|c| c.frame_intern_new += 1);
            self.tc_cache.frames.insert_at(vacant, hash, e);
        } else {
            // A hash match with a distinct source frame must not be unified.
            count_prune(|c| c.frame_intern_hash_collisions += 1);
        }""")
s=s[:start]+a+s[end:]
assert s.count("MG_PRUNE_CENSUS_THREAD=")==1
p.write_text(s)
print("PRUNE_CAUSAL_CENSUS_INSTRUMENTATION=ADDED_DIAGNOSTIC_ONLY",flush=True)
