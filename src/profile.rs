use std::sync::OnceLock;
use std::sync::atomic::{AtomicU64, Ordering};

const SEEN_BITS: usize = 18;
const SEEN_LEN: usize = 1 << SEEN_BITS;
static SEEN: [AtomicU64; SEEN_LEN] = [const { AtomicU64::new(0) }; SEEN_LEN];

static ENABLED: OnceLock<bool> = OnceLock::new();

static LEVEL_EQ_CALLS: AtomicU64 = AtomicU64::new(0);
static LEVEL_EQ_PTR: AtomicU64 = AtomicU64::new(0);
static LEVEL_EQ_SIMPLIFIED_PTR: AtomicU64 = AtomicU64::new(0);
static LEVEL_EQ_RECURSIVE: AtomicU64 = AtomicU64::new(0);
static LEVEL_EQ_RECURSIVE_TRUE: AtomicU64 = AtomicU64::new(0);
static LEVEL_EQ_RECURSIVE_FALSE: AtomicU64 = AtomicU64::new(0);

static SPINE_PROBE_CALLS: AtomicU64 = AtomicU64::new(0);
static SPINE_PTR_EQUAL: AtomicU64 = AtomicU64::new(0);
static SPINE_BOTH_CLOSED: AtomicU64 = AtomicU64::new(0);
static SPINE_REPEAT: AtomicU64 = AtomicU64::new(0);
static SPINE_REPEAT_CLOSED: AtomicU64 = AtomicU64::new(0);
static SPINE_REPEAT_TRUE: AtomicU64 = AtomicU64::new(0);
static SPINE_REPEAT_FALSE: AtomicU64 = AtomicU64::new(0);
static SPINE_FIRST_TRUE: AtomicU64 = AtomicU64::new(0);
static SPINE_FIRST_FALSE: AtomicU64 = AtomicU64::new(0);

#[inline]
pub fn enabled() -> bool {
    *ENABLED.get_or_init(|| std::env::var_os("QCKN_R3B_PROFILE").is_some())
}

#[inline]
fn inc(x: &AtomicU64) {
    if enabled() {
        x.fetch_add(1, Ordering::Relaxed);
    }
}

#[inline]
pub fn note_level_ptr_equal() {
    inc(&LEVEL_EQ_CALLS);
    inc(&LEVEL_EQ_PTR);
}

#[inline]
pub fn note_level_simplified_equal() {
    inc(&LEVEL_EQ_CALLS);
    inc(&LEVEL_EQ_SIMPLIFIED_PTR);
}

#[inline]
pub fn note_level_recursive(ok: bool) {
    inc(&LEVEL_EQ_CALLS);
    inc(&LEVEL_EQ_RECURSIVE);
    if ok { inc(&LEVEL_EQ_RECURSIVE_TRUE); } else { inc(&LEVEL_EQ_RECURSIVE_FALSE); }
}

#[inline]
fn mix(mut x: u64) -> u64 {
    x ^= x >> 30;
    x = x.wrapping_mul(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

#[inline]
pub fn spine_probe_seen(a: usize, b: usize, depth: u32, limit: u32, sig_hash: u64, both_closed: bool, ptr_equal: bool) -> bool {
    if !enabled() {
        return false;
    }
    inc(&SPINE_PROBE_CALLS);
    if ptr_equal {
        inc(&SPINE_PTR_EQUAL);
    }
    if both_closed {
        inc(&SPINE_BOTH_CLOSED);
    }

    let (lo, hi) = if a <= b { (a as u64, b as u64) } else { (b as u64, a as u64) };
    let mut key = mix(lo ^ hi.rotate_left(17));
    key ^= mix(u64::from(depth) << 32 | u64::from(limit));
    key ^= mix(sig_hash);
    key |= 1;
    let slot = (key as usize) & (SEEN_LEN - 1);
    let old = SEEN[slot].swap(key, Ordering::Relaxed);
    let repeat = old == key;
    if repeat {
        inc(&SPINE_REPEAT);
        if both_closed {
            inc(&SPINE_REPEAT_CLOSED);
        }
    }
    repeat
}

#[inline]
pub fn note_spine_probe_result(repeat: bool, ok: bool) {
    if !enabled() {
        return;
    }
    match (repeat, ok) {
        (true, true) => inc(&SPINE_REPEAT_TRUE),
        (true, false) => inc(&SPINE_REPEAT_FALSE),
        (false, true) => inc(&SPINE_FIRST_TRUE),
        (false, false) => inc(&SPINE_FIRST_FALSE),
    }
}

#[inline]
fn load(x: &AtomicU64) -> u64 { x.load(Ordering::Relaxed) }

pub fn report() {
    if !enabled() {
        return;
    }
    eprintln!(
        concat!(
            "QCKN_R3B_PROFILE ",
            "level_eq_calls={} level_eq_ptr={} level_eq_simplified_ptr={} level_eq_recursive={} ",
            "level_eq_recursive_true={} level_eq_recursive_false={} ",
            "spine_probe_calls={} spine_ptr_equal={} spine_both_closed={} ",
            "spine_repeat={} spine_repeat_closed={} spine_repeat_true={} spine_repeat_false={} ",
            "spine_first_true={} spine_first_false={}"
        ),
        load(&LEVEL_EQ_CALLS),
        load(&LEVEL_EQ_PTR),
        load(&LEVEL_EQ_SIMPLIFIED_PTR),
        load(&LEVEL_EQ_RECURSIVE),
        load(&LEVEL_EQ_RECURSIVE_TRUE),
        load(&LEVEL_EQ_RECURSIVE_FALSE),
        load(&SPINE_PROBE_CALLS),
        load(&SPINE_PTR_EQUAL),
        load(&SPINE_BOTH_CLOSED),
        load(&SPINE_REPEAT),
        load(&SPINE_REPEAT_CLOSED),
        load(&SPINE_REPEAT_TRUE),
        load(&SPINE_REPEAT_FALSE),
        load(&SPINE_FIRST_TRUE),
        load(&SPINE_FIRST_FALSE),
    );
}
