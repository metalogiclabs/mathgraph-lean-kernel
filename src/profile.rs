use std::sync::OnceLock;
use std::sync::atomic::{AtomicU64, Ordering};

pub const CLASS_NAMES: [&str; 23] = [
    "sort_sort",
    "natlit_natlit",
    "strlit_strlit",
    "pi_pi",
    "lam_lam",
    "unfold_same",
    "unfold_diff",
    "unfold_other",
    "other_unfold",
    "rec_same",
    "rec_diff",
    "quot_same",
    "quot_diff",
    "recquot_other",
    "other_recquot",
    "ctor_same",
    "inductive_same",
    "axiom_same",
    "bvar_pair",
    "lam_other",
    "other_lam",
    "rigid_other",
    "other",
];

const N: usize = CLASS_NAMES.len();

static ENABLED: OnceLock<bool> = OnceLock::new();

static CALLS: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static UF_HITS: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static NEG_HITS: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static PROBE_NEG_HITS: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static FRESH: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static NAT_RESOLVED: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static DIRECT_TRUE: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static DIRECT_FALSE: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static COLD_TRUE: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
static COLD_FALSE: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];

static SPINE_PROBE_ATTEMPT: AtomicU64 = AtomicU64::new(0);
static SPINE_PROBE_HIT: AtomicU64 = AtomicU64::new(0);
static UNFOLD_PAIR_ATTEMPT: AtomicU64 = AtomicU64::new(0);
static UNFOLD_PAIR_HIT: AtomicU64 = AtomicU64::new(0);
static IOTA_PAIR_ATTEMPT: AtomicU64 = AtomicU64::new(0);
static IOTA_PAIR_HIT: AtomicU64 = AtomicU64::new(0);
static PROOF_IRREL_ATTEMPT: AtomicU64 = AtomicU64::new(0);
static PROOF_IRREL_HIT: AtomicU64 = AtomicU64::new(0);
static STRUCT_ETA_ATTEMPT: AtomicU64 = AtomicU64::new(0);
static STRUCT_ETA_HIT: AtomicU64 = AtomicU64::new(0);

#[inline]
pub fn enabled() -> bool {
    *ENABLED.get_or_init(|| std::env::var_os("QCKN_R3A_PROFILE").is_some())
}

#[inline]
fn inc(x: &AtomicU64) {
    if enabled() {
        x.fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_call(class: usize) {
    if enabled() {
        CALLS[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_uf_hit(class: usize) {
    if enabled() {
        UF_HITS[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_neg_hit(class: usize) {
    if enabled() {
        NEG_HITS[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_probe_neg_hit(class: usize) {
    if enabled() {
        PROBE_NEG_HITS[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_fresh(class: usize) {
    if enabled() {
        FRESH[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_nat_resolved(class: usize) {
    if enabled() {
        NAT_RESOLVED[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_direct(class: usize, ok: bool) {
    if !enabled() {
        return;
    }
    if ok {
        DIRECT_TRUE[class].fetch_add(1, Ordering::Relaxed);
    } else {
        DIRECT_FALSE[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_cold(class: usize, ok: bool) {
    if !enabled() {
        return;
    }
    if ok {
        COLD_TRUE[class].fetch_add(1, Ordering::Relaxed);
    } else {
        COLD_FALSE[class].fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_spine_probe(ok: bool) {
    inc(&SPINE_PROBE_ATTEMPT);
    if ok { inc(&SPINE_PROBE_HIT); }
}

#[inline]
pub fn note_unfold_pair(ok: bool) {
    inc(&UNFOLD_PAIR_ATTEMPT);
    if ok { inc(&UNFOLD_PAIR_HIT); }
}

#[inline]
pub fn note_iota_pair(ok: bool) {
    inc(&IOTA_PAIR_ATTEMPT);
    if ok { inc(&IOTA_PAIR_HIT); }
}

#[inline]
pub fn note_proof_irrel(ok: bool) {
    inc(&PROOF_IRREL_ATTEMPT);
    if ok { inc(&PROOF_IRREL_HIT); }
}

#[inline]
pub fn note_struct_eta(ok: bool) {
    inc(&STRUCT_ETA_ATTEMPT);
    if ok { inc(&STRUCT_ETA_HIT); }
}

#[inline]
fn load(x: &AtomicU64) -> u64 {
    x.load(Ordering::Relaxed)
}

pub fn report() {
    if !enabled() {
        return;
    }

    let total_calls: u64 = CALLS.iter().map(load).sum();
    let total_fresh: u64 = FRESH.iter().map(load).sum();
    let total_uf: u64 = UF_HITS.iter().map(load).sum();
    let total_neg: u64 = NEG_HITS.iter().map(load).sum();
    let total_probe_neg: u64 = PROBE_NEG_HITS.iter().map(load).sum();

    eprintln!(
        "QCKN_R3A_SUMMARY calls={} fresh={} uf_hits={} neg_hits={} probe_neg_hits={} spine_probe_attempt={} spine_probe_hit={} unfold_pair_attempt={} unfold_pair_hit={} iota_pair_attempt={} iota_pair_hit={} proof_irrel_attempt={} proof_irrel_hit={} struct_eta_attempt={} struct_eta_hit={}",
        total_calls,
        total_fresh,
        total_uf,
        total_neg,
        total_probe_neg,
        load(&SPINE_PROBE_ATTEMPT),
        load(&SPINE_PROBE_HIT),
        load(&UNFOLD_PAIR_ATTEMPT),
        load(&UNFOLD_PAIR_HIT),
        load(&IOTA_PAIR_ATTEMPT),
        load(&IOTA_PAIR_HIT),
        load(&PROOF_IRREL_ATTEMPT),
        load(&PROOF_IRREL_HIT),
        load(&STRUCT_ETA_ATTEMPT),
        load(&STRUCT_ETA_HIT),
    );

    for (i, name) in CLASS_NAMES.iter().enumerate() {
        let calls = load(&CALLS[i]);
        if calls == 0 {
            continue;
        }
        eprintln!(
            "QCKN_R3A_CLASS name={} calls={} fresh={} uf_hits={} neg_hits={} probe_neg_hits={} nat_resolved={} direct_true={} direct_false={} cold_true={} cold_false={}",
            name,
            calls,
            load(&FRESH[i]),
            load(&UF_HITS[i]),
            load(&NEG_HITS[i]),
            load(&PROBE_NEG_HITS[i]),
            load(&NAT_RESOLVED[i]),
            load(&DIRECT_TRUE[i]),
            load(&DIRECT_FALSE[i]),
            load(&COLD_TRUE[i]),
            load(&COLD_FALSE[i]),
        );
    }
}
