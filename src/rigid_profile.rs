use std::sync::OnceLock;
use std::sync::atomic::{AtomicU64, Ordering};

static ENABLED: OnceLock<bool> = OnceLock::new();

static TOTAL: AtomicU64 = AtomicU64::new(0);
static F_CANONICAL: AtomicU64 = AtomicU64::new(0);
static A_CANONICAL: AtomicU64 = AtomicU64::new(0);
static APP_HC_HIT: AtomicU64 = AtomicU64::new(0);
static APP_HC_MISS: AtomicU64 = AtomicU64::new(0);
static SPINE_0: AtomicU64 = AtomicU64::new(0);
static SPINE_1: AtomicU64 = AtomicU64::new(0);
static SPINE_2_3: AtomicU64 = AtomicU64::new(0);
static SPINE_4_7: AtomicU64 = AtomicU64::new(0);
static SPINE_8_PLUS: AtomicU64 = AtomicU64::new(0);

#[inline]
pub(crate) fn enabled() -> bool {
    *ENABLED.get_or_init(|| std::env::var_os("QCKN_FLASH_RIGID_INTERFACE_PROFILE").is_some())
}

#[inline]
fn inc(x: &AtomicU64) {
    if enabled() {
        x.fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub(crate) fn note_pre(f_canonical: bool, a_canonical: bool, spine_len: u32) {
    if !enabled() {
        return;
    }
    inc(&TOTAL);
    if f_canonical { inc(&F_CANONICAL); }
    if a_canonical { inc(&A_CANONICAL); }
    match spine_len {
        0 => inc(&SPINE_0),
        1 => inc(&SPINE_1),
        2..=3 => inc(&SPINE_2_3),
        4..=7 => inc(&SPINE_4_7),
        _ => inc(&SPINE_8_PLUS),
    }
}

#[inline]
pub(crate) fn note_app_hc(hit: bool) {
    if !enabled() {
        return;
    }
    if hit { inc(&APP_HC_HIT); } else { inc(&APP_HC_MISS); }
}

#[inline]
fn load(x: &AtomicU64) -> u64 { x.load(Ordering::Relaxed) }

pub fn report() {
    if !enabled() {
        return;
    }
    eprintln!(
        concat!(
            "QCKN_FLASH_RIGID_INTERFACE ",
            "total={} f_canonical={} a_canonical={} app_hc_hit={} app_hc_miss={} ",
            "spine_0={} spine_1={} spine_2_3={} spine_4_7={} spine_8_plus={}"
        ),
        load(&TOTAL),
        load(&F_CANONICAL),
        load(&A_CANONICAL),
        load(&APP_HC_HIT),
        load(&APP_HC_MISS),
        load(&SPINE_0),
        load(&SPINE_1),
        load(&SPINE_2_3),
        load(&SPINE_4_7),
        load(&SPINE_8_PLUS),
    );
}
