//! Diagnostic-only source-identity reuse census.
//!
//! The census observes cache misses; it NEVER reuses a value or authorizes
//! equivalence. A repeated key across resets is only an opportunity candidate.

use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MissClass {
    Excluded,
    First,
    SameGeneration,
    AcrossGenerationCandidate,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct ProbeStats {
    pub sampled_cache_hits: u64,
    pub excluded: u64,
    pub first: u64,
    pub same_generation: u64,
    pub across_generation_candidate: u64,
    pub cache_resets: u64,
}

#[derive(Debug, Default)]
pub struct ReuseProbe {
    generation: u64,
    seen: HashMap<(u64, u64), u64>,
    stats: ProbeStats,
}

impl ReuseProbe {
    /// Deterministic 1/256 sample for bounded-memory runs. The input identity
    /// must be stable over the lifetime of the source; this is NOT a fingerprint
    /// for cross-process or cross-source semantic equivalence.
    pub fn in_sample(identity: u64) -> bool {
        let mut x = identity ^ (identity >> 30);
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        x ^= x >> 31;
        x & 255 == 0
    }

    pub fn cache_reset(&mut self) {
        self.generation = self.generation.wrapping_add(1);
        self.stats.cache_resets += 1;
    }

    pub fn sampled_cache_hit(&mut self) {
        self.stats.sampled_cache_hits += 1;
    }

    pub fn observe_miss(
        &mut self,
        source_epoch: u64,
        identity: u64,
        source_global: bool,
        closed_and_unsubstituted: bool,
    ) -> MissClass {
        if !source_global || !closed_and_unsubstituted {
            self.stats.excluded += 1;
            return MissClass::Excluded;
        }
        let key = (source_epoch, identity);
        let result = match self.seen.insert(key, self.generation) {
            None => {
                self.stats.first += 1;
                MissClass::First
            }
            Some(g) if g == self.generation => {
                self.stats.same_generation += 1;
                MissClass::SameGeneration
            }
            Some(_) => {
                self.stats.across_generation_candidate += 1;
                MissClass::AcrossGenerationCandidate
            }
        };
        result
    }

    pub fn stats(&self) -> ProbeStats {
        self.stats
    }

    pub fn report(&self) -> serde_json::Value {
        report_from_stats(self.stats)
    }
}

fn report_from_stats(stats: ProbeStats) -> serde_json::Value {
    serde_json::json!({
        "qualification": "CANDIDATE_IDENTITY_ONLY",
        "speedup_measured": false,
        "basis": "sampled source-global closed unsubstituted expression identity",
        "sample_denominator": 256,
        "excluded_from_warrant": [
            "possible source-environment visibility differences",
            "expression-identity recurrence does not establish typed semantic equivalence",
            "cache-reset candidates are not proven safely reusable",
            "call counts do not measure avoided machine instructions"
        ],
        "counts": {
            "sampled_cache_hits": stats.sampled_cache_hits,
            "excluded": stats.excluded,
            "first": stats.first,
            "same_generation": stats.same_generation,
            "across_generation_candidate": stats.across_generation_candidate,
            "cache_resets": stats.cache_resets,
        }
    })
}

#[cfg(feature = "reuse-probe")]
mod global_report {
    use super::{report_from_stats, ProbeStats, ReuseProbe};
    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};

    static HITS: AtomicU64 = AtomicU64::new(0);
    static EXCLUDED: AtomicU64 = AtomicU64::new(0);
    static FIRST: AtomicU64 = AtomicU64::new(0);
    static SAME: AtomicU64 = AtomicU64::new(0);
    static REVISITS: AtomicU64 = AtomicU64::new(0);
    static RESETS: AtomicU64 = AtomicU64::new(0);

    impl Drop for ReuseProbe {
        fn drop(&mut self) {
            let s = self.stats;
            HITS.fetch_add(s.sampled_cache_hits, Relaxed);
            EXCLUDED.fetch_add(s.excluded, Relaxed);
            FIRST.fetch_add(s.first, Relaxed);
            SAME.fetch_add(s.same_generation, Relaxed);
            REVISITS.fetch_add(s.across_generation_candidate, Relaxed);
            RESETS.fetch_add(s.cache_resets, Relaxed);
        }
    }

    pub fn global_report() -> serde_json::Value {
        report_from_stats(ProbeStats {
            sampled_cache_hits: HITS.load(Relaxed),
            excluded: EXCLUDED.load(Relaxed),
            first: FIRST.load(Relaxed),
            same_generation: SAME.load(Relaxed),
            across_generation_candidate: REVISITS.load(Relaxed),
            cache_resets: RESETS.load(Relaxed),
        })
    }
}

#[cfg(feature = "reuse-probe")]
pub use global_report::global_report;
