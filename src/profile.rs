use std::sync::OnceLock;
use std::sync::atomic::{AtomicU64, Ordering};

static ENABLED: OnceLock<bool> = OnceLock::new();

static KEY_ENV_CALLS: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_BEFORE: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_AFTER: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_REDUCED: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_HALF: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_QUARTER: AtomicU64 = AtomicU64::new(0);
static KEY_ENV_WIDE: AtomicU64 = AtomicU64::new(0);

static APPLY_CLOSURE: AtomicU64 = AtomicU64::new(0);
static APPLY_CLOSURE_INFER: AtomicU64 = AtomicU64::new(0);

static FORCE_ALL_CALLS: AtomicU64 = AtomicU64::new(0);
static FORCE_ALL_STORE_HITS: AtomicU64 = AtomicU64::new(0);
static FORCE_ALL_NONZERO: AtomicU64 = AtomicU64::new(0);
static FORCE_ALL_STEPS: AtomicU64 = AtomicU64::new(0);
static FORCE_ALL_GE4: AtomicU64 = AtomicU64::new(0);
static FORCE_ALL_GE16: AtomicU64 = AtomicU64::new(0);

static CONV_TOP_CALLS: AtomicU64 = AtomicU64::new(0);
static CONV_CACHEABLE: AtomicU64 = AtomicU64::new(0);
static CONV_UF_HITS: AtomicU64 = AtomicU64::new(0);
static CONV_NEG_HITS: AtomicU64 = AtomicU64::new(0);
static CONV_PROBE_NEG_HITS: AtomicU64 = AtomicU64::new(0);
static CONV_COLD: AtomicU64 = AtomicU64::new(0);

static INFER_CACHE_HITS: AtomicU64 = AtomicU64::new(0);
static INFER_CACHE_MISSES: AtomicU64 = AtomicU64::new(0);

static CLOSED_EVAL_HITS: AtomicU64 = AtomicU64::new(0);
static CLOSED_EVAL_MISSES: AtomicU64 = AtomicU64::new(0);
static OPEN_EVAL_HITS: AtomicU64 = AtomicU64::new(0);
static OPEN_EVAL_MISSES: AtomicU64 = AtomicU64::new(0);

#[inline]
pub fn enabled() -> bool {
    *ENABLED.get_or_init(|| std::env::var_os("QCKN_PROFILE").is_some())
}

#[inline]
fn inc(c: &AtomicU64) {
    if enabled() {
        c.fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
fn add(c: &AtomicU64, n: u64) {
    if enabled() {
        c.fetch_add(n, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_key_env(before: u32, after: u32, wide: bool) {
    if !enabled() {
        return;
    }
    KEY_ENV_CALLS.fetch_add(1, Ordering::Relaxed);
    KEY_ENV_BEFORE.fetch_add(u64::from(before), Ordering::Relaxed);
    KEY_ENV_AFTER.fetch_add(u64::from(after), Ordering::Relaxed);
    if wide {
        KEY_ENV_WIDE.fetch_add(1, Ordering::Relaxed);
    }
    if after < before {
        KEY_ENV_REDUCED.fetch_add(1, Ordering::Relaxed);
    }
    if before >= 2 && after.saturating_mul(2) <= before {
        KEY_ENV_HALF.fetch_add(1, Ordering::Relaxed);
    }
    if before >= 4 && after.saturating_mul(4) <= before {
        KEY_ENV_QUARTER.fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_apply_closure(infer: bool) {
    inc(&APPLY_CLOSURE);
    if infer {
        inc(&APPLY_CLOSURE_INFER);
    }
}

#[inline]
pub fn note_force_all_store_hit() {
    inc(&FORCE_ALL_CALLS);
    inc(&FORCE_ALL_STORE_HITS);
}

#[inline]
pub fn note_force_all(steps: u32) {
    inc(&FORCE_ALL_CALLS);
    if steps > 0 {
        inc(&FORCE_ALL_NONZERO);
        add(&FORCE_ALL_STEPS, u64::from(steps));
    }
    if steps >= 4 {
        inc(&FORCE_ALL_GE4);
    }
    if steps >= 16 {
        inc(&FORCE_ALL_GE16);
    }
}

#[inline]
pub fn note_conv_top() {
    inc(&CONV_TOP_CALLS);
}

#[inline]
pub fn note_conv_cacheable() {
    inc(&CONV_CACHEABLE);
}

#[inline]
pub fn note_conv_uf_hit() {
    inc(&CONV_UF_HITS);
}

#[inline]
pub fn note_conv_neg_hit() {
    inc(&CONV_NEG_HITS);
}

#[inline]
pub fn note_conv_probe_neg_hit() {
    inc(&CONV_PROBE_NEG_HITS);
}

#[inline]
pub fn note_conv_cold() {
    inc(&CONV_COLD);
}

#[inline]
pub fn note_infer_cache(hit: bool) {
    if hit {
        inc(&INFER_CACHE_HITS);
    } else {
        inc(&INFER_CACHE_MISSES);
    }
}

#[inline]
pub fn note_eval_cache(open: bool, hit: bool) {
    match (open, hit) {
        (false, true) => inc(&CLOSED_EVAL_HITS),
        (false, false) => inc(&CLOSED_EVAL_MISSES),
        (true, true) => inc(&OPEN_EVAL_HITS),
        (true, false) => inc(&OPEN_EVAL_MISSES),
    }
}

fn load(c: &AtomicU64) -> u64 {
    c.load(Ordering::Relaxed)
}

pub fn report() {
    if !enabled() {
        return;
    }
    eprintln!(
        concat!(
            "QCKN_PROFILE ",
            "key_env_calls={} key_env_before={} key_env_after={} key_env_reduced={} ",
            "key_env_half={} key_env_quarter={} key_env_wide={} ",
            "apply_closure={} apply_closure_infer={} ",
            "force_all_calls={} force_all_store_hits={} force_all_nonzero={} force_all_steps={} ",
            "force_all_ge4={} force_all_ge16={} ",
            "conv_top_calls={} conv_cacheable={} conv_uf_hits={} conv_neg_hits={} ",
            "conv_probe_neg_hits={} conv_cold={} ",
            "infer_cache_hits={} infer_cache_misses={} ",
            "closed_eval_hits={} closed_eval_misses={} open_eval_hits={} open_eval_misses={}"
        ),
        load(&KEY_ENV_CALLS),
        load(&KEY_ENV_BEFORE),
        load(&KEY_ENV_AFTER),
        load(&KEY_ENV_REDUCED),
        load(&KEY_ENV_HALF),
        load(&KEY_ENV_QUARTER),
        load(&KEY_ENV_WIDE),
        load(&APPLY_CLOSURE),
        load(&APPLY_CLOSURE_INFER),
        load(&FORCE_ALL_CALLS),
        load(&FORCE_ALL_STORE_HITS),
        load(&FORCE_ALL_NONZERO),
        load(&FORCE_ALL_STEPS),
        load(&FORCE_ALL_GE4),
        load(&FORCE_ALL_GE16),
        load(&CONV_TOP_CALLS),
        load(&CONV_CACHEABLE),
        load(&CONV_UF_HITS),
        load(&CONV_NEG_HITS),
        load(&CONV_PROBE_NEG_HITS),
        load(&CONV_COLD),
        load(&INFER_CACHE_HITS),
        load(&INFER_CACHE_MISSES),
        load(&CLOSED_EVAL_HITS),
        load(&CLOSED_EVAL_MISSES),
        load(&OPEN_EVAL_HITS),
        load(&OPEN_EVAL_MISSES),
    );
}
