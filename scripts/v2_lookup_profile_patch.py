from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/value.rs"
s = p.read_text()

s = s.replace(
    "use std::cell::{Cell, OnceCell};",
    "use std::cell::{Cell, OnceCell};\nuse std::sync::atomic::{AtomicU64, Ordering};",
    1,
)

marker = "pub type S<'a> = &'a Spine<'a>;\n"
assert marker in s
stats = r'''

static LOOKUP_CALLS: AtomicU64 = AtomicU64::new(0);
static LOOKUP_STEPS: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX0: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX1_7: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX8_31: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX32_127: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX128P: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_LE64: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_65_255: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_256_1023: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_1024P: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX_SUM: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_SUM: AtomicU64 = AtomicU64::new(0);
static LOOKUP_IDX_MAX: AtomicU64 = AtomicU64::new(0);
static LOOKUP_ENV_MAX: AtomicU64 = AtomicU64::new(0);

#[inline]
fn atomic_max(cell: &AtomicU64, x: u64) {
    let mut cur = cell.load(Ordering::Relaxed);
    while x > cur {
        match cell.compare_exchange_weak(cur, x, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => break,
            Err(actual) => cur = actual,
        }
    }
}

#[inline]
fn note_lookup(idx: u16, env_len: u32) {
    let i = u64::from(idx);
    let l = u64::from(env_len);
    LOOKUP_CALLS.fetch_add(1, Ordering::Relaxed);
    LOOKUP_IDX_SUM.fetch_add(i, Ordering::Relaxed);
    LOOKUP_ENV_SUM.fetch_add(l, Ordering::Relaxed);
    atomic_max(&LOOKUP_IDX_MAX, i);
    atomic_max(&LOOKUP_ENV_MAX, l);
    match idx {
        0 => { LOOKUP_IDX0.fetch_add(1, Ordering::Relaxed); }
        1..=7 => { LOOKUP_IDX1_7.fetch_add(1, Ordering::Relaxed); }
        8..=31 => { LOOKUP_IDX8_31.fetch_add(1, Ordering::Relaxed); }
        32..=127 => { LOOKUP_IDX32_127.fetch_add(1, Ordering::Relaxed); }
        _ => { LOOKUP_IDX128P.fetch_add(1, Ordering::Relaxed); }
    }
    match env_len {
        0..=64 => { LOOKUP_ENV_LE64.fetch_add(1, Ordering::Relaxed); }
        65..=255 => { LOOKUP_ENV_65_255.fetch_add(1, Ordering::Relaxed); }
        256..=1023 => { LOOKUP_ENV_256_1023.fetch_add(1, Ordering::Relaxed); }
        _ => { LOOKUP_ENV_1024P.fetch_add(1, Ordering::Relaxed); }
    }
}

#[inline]
fn note_lookup_step() {
    LOOKUP_STEPS.fetch_add(1, Ordering::Relaxed);
}

pub fn dump_lookup_profile() {
    let calls = LOOKUP_CALLS.load(Ordering::Relaxed);
    let steps = LOOKUP_STEPS.load(Ordering::Relaxed);
    let avg_idx = if calls == 0 { 0.0 } else { LOOKUP_IDX_SUM.load(Ordering::Relaxed) as f64 / calls as f64 };
    let avg_env = if calls == 0 { 0.0 } else { LOOKUP_ENV_SUM.load(Ordering::Relaxed) as f64 / calls as f64 };
    eprintln!(
        "LOOKUP_PROFILE calls={} steps={} steps_per_call={:.6} avg_idx={:.6} max_idx={} avg_env_len={:.6} max_env_len={} idx0={} idx1_7={} idx8_31={} idx32_127={} idx128p={} env_le64={} env65_255={} env256_1023={} env1024p={}",
        calls,
        steps,
        if calls == 0 { 0.0 } else { steps as f64 / calls as f64 },
        avg_idx,
        LOOKUP_IDX_MAX.load(Ordering::Relaxed),
        avg_env,
        LOOKUP_ENV_MAX.load(Ordering::Relaxed),
        LOOKUP_IDX0.load(Ordering::Relaxed),
        LOOKUP_IDX1_7.load(Ordering::Relaxed),
        LOOKUP_IDX8_31.load(Ordering::Relaxed),
        LOOKUP_IDX32_127.load(Ordering::Relaxed),
        LOOKUP_IDX128P.load(Ordering::Relaxed),
        LOOKUP_ENV_LE64.load(Ordering::Relaxed),
        LOOKUP_ENV_65_255.load(Ordering::Relaxed),
        LOOKUP_ENV_256_1023.load(Ordering::Relaxed),
        LOOKUP_ENV_1024P.load(Ordering::Relaxed),
    );
}
'''
s = s.replace(marker, marker + stats, 1)

# Instrument Env::lookup only. The fixed-stride and lowbit variants use a
# non-mut idx signature while baseline uses mut idx, and Ctx::lookup later in
# the file also uses mut idx. Restrict the search to the Env impl so the latter
# cannot be mistaken for the baseline Env method.
env_start = s.index("impl<'a> Env<'a> {\n    pub fn lookup")
env_end = s.index("impl<'a> Closure<'a>", env_start)
prefix = s[:env_start]
env_body = s[env_start:env_end]
suffix = s[env_end:]

needle_mut = "    pub fn lookup(&self, mut idx: u16) -> Option<V<'a>> {\n"
needle_plain = "    pub fn lookup(&self, idx: u16) -> Option<V<'a>> {\n"
if needle_mut in env_body:
    env_body = env_body.replace(needle_mut, needle_mut + "        note_lookup(idx, self.len());\n", 1)
elif needle_plain in env_body:
    env_body = env_body.replace(needle_plain, needle_plain + "        note_lookup(idx, self.len());\n", 1)
else:
    raise AssertionError("Env lookup signature not found")

loop = "        loop {\n            match cur {"
assert loop in env_body
env_body = env_body.replace(loop, "        loop {\n            note_lookup_step();\n            match cur {", 1)
s = prefix + env_body + suffix
p.write_text(s)

m = root / "src/main.rs"
ms = m.read_text()
needle = "    match out {\n"
assert needle in ms
ms = ms.replace(needle, "    sokonanoda::value::dump_lookup_profile();\n    match out {\n", 1)
m.write_text(ms)
