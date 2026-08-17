from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/value.rs"
s = p.read_text()

# This patch is applied after v2_lookup_profile_patch.py, so AtomicU64 and
# Ordering are already imported. Keep the additional counters orthogonal to
# lookup-request instrumentation: they measure the cost of constructing the
# environment navigation structure itself.
marker = "pub type S<'a> = &'a Spine<'a>;\n"
assert marker in s
stats = r'''

static ENV_EXTENDS: AtomicU64 = AtomicU64::new(0);
static ENV_EXTEND_WALK_STEPS: AtomicU64 = AtomicU64::new(0);

#[inline]
fn note_env_extend() {
    ENV_EXTENDS.fetch_add(1, Ordering::Relaxed);
}

#[inline]
fn note_env_extend_walk_step() {
    ENV_EXTEND_WALK_STEPS.fetch_add(1, Ordering::Relaxed);
}

pub fn dump_cost_profile() {
    let extends = ENV_EXTENDS.load(Ordering::Relaxed);
    let walk = ENV_EXTEND_WALK_STEPS.load(Ordering::Relaxed);
    eprintln!(
        "COST_PROFILE env_extends={} extend_walk_steps={} walk_per_extend={:.6} env_size={}",
        extends,
        walk,
        if extends == 0 { 0.0 } else { walk as f64 / extends as f64 },
        std::mem::size_of::<Env<'static>>(),
    );
}
'''
s = s.replace(marker, marker + stats, 1)

# Count every persistent environment extension for all arms.
needle = "pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {\n"
assert needle in s
s = s.replace(needle, needle + "    note_env_extend();\n", 1)

# Count only the navigation work required to construct the extra index.
# Baseline has no such loop. jump32 walks up to 31 parent links per extension;
# lowbit walks the existing hierarchy while constructing its one skip pointer.
if "for _ in 1..32 {\n        jump = match jump {" in s:
    s = s.replace(
        "for _ in 1..32 {\n        jump = match jump {",
        "for _ in 1..32 {\n        note_env_extend_walk_step();\n        jump = match jump {",
        1,
    )
elif "while remaining != 0 {\n        match jump {" in s:
    s = s.replace(
        "while remaining != 0 {\n        match jump {",
        "while remaining != 0 {\n        note_env_extend_walk_step();\n        match jump {",
        1,
    )
# Else: baseline arm, intentionally zero construction-walk steps.

p.write_text(s)

m = root / "src/main.rs"
ms = m.read_text()
needle_main = "    sokonanoda::value::dump_lookup_profile();\n    match out {\n"
assert needle_main in ms
ms = ms.replace(
    needle_main,
    "    sokonanoda::value::dump_lookup_profile();\n    sokonanoda::value::dump_cost_profile();\n    match out {\n",
    1,
)
m.write_text(ms)
