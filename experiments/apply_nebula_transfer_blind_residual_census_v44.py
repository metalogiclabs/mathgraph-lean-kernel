from pathlib import Path

p = Path("src/eval.rs")
s = p.read_text()

import_anchor = "use std::cell::OnceCell;\n"
if import_anchor not in s:
    raise SystemExit("V44_EVAL_IMPORT_ANCHOR_MISSING")
s = s.replace(
    import_anchor,
    import_anchor + "use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n",
    1,
)

type_anchor = "pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;\n"
if type_anchor not in s:
    raise SystemExit("V44_EVAL_TYPE_ANCHOR_MISSING")

instrumentation = r"""
const V44_KIND_COUNT: usize = 8;
const V44_FAMILY_COUNT: usize = 5;
static V44_COUNTS: [AtomicU64; V44_KIND_COUNT * V44_FAMILY_COUNT] =
    [const { AtomicU64::new(0) }; V44_KIND_COUNT * V44_FAMILY_COUNT];
static V44_FORCE_CALLS: AtomicU64 = AtomicU64::new(0);

#[inline]
fn v44_value_kind(v: V<'_>) -> usize {
    match v {
        Value::Rigid { .. } => 0,
        Value::Unfold { .. } => 1,
        Value::Lam { .. } => 2,
        Value::Pi { .. } => 3,
        Value::Sort { .. } => 4,
        Value::NatLit { .. } => 5,
        Value::StrLit { .. } => 6,
        Value::Thunk { .. } => 7,
    }
}

#[inline]
fn v44_kind_name(k: usize) -> &'static str {
    match k {
        0 => "Rigid",
        1 => "Unfold",
        2 => "Lam",
        3 => "Pi",
        4 => "Sort",
        5 => "NatLit",
        6 => "StrLit",
        7 => "Thunk",
        _ => "Unknown",
    }
}

#[inline]
fn v44_note(family: usize, v: V<'_>) {
    let kind = v44_value_kind(v);
    V44_COUNTS[family * V44_KIND_COUNT + kind].fetch_add(1, Relaxed);
}

pub(crate) fn v44_transfer_report() {
    let families = ["whnf", "apply", "projection", "unfold", "iota"];
    for (family, name) in families.iter().enumerate() {
        let mut counts = [0u64; V44_KIND_COUNT];
        for (kind, slot) in counts.iter_mut().enumerate() {
            *slot = V44_COUNTS[family * V44_KIND_COUNT + kind].load(Relaxed);
        }
        let total: u64 = counts.iter().sum();
        let (dominant, dominant_calls) = counts
            .iter()
            .copied()
            .enumerate()
            .max_by_key(|&(kind, n)| (n, std::cmp::Reverse(kind)))
            .unwrap();
        eprintln!(
            "V44_FAMILY family={} total={} dominant={} dominant_calls={} counts={},{},{},{},{},{},{},{}",
            name,
            total,
            v44_kind_name(dominant),
            dominant_calls,
            counts[0], counts[1], counts[2], counts[3],
            counts[4], counts[5], counts[6], counts[7],
        );
    }
    eprintln!("V44_FORCE force_calls={}", V44_FORCE_CALLS.load(Relaxed));
    eprintln!("V44_RULE=blind_cold_selector_then_exact_replay");
}

"""
s = s.replace(type_anchor, type_anchor + instrumentation, 1)

anchors = [
    (
        "    pub(crate) fn whnf_head(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n",
        "    pub(crate) fn whnf_head(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        v44_note(0, v);\n",
        "V44_WHNF_ANCHOR_MISSING",
    ),
    (
        "    pub(crate) fn apply(&mut self, depth: u32, f: V<'t>, a: V<'t>) -> V<'t> {\n",
        "    pub(crate) fn apply(&mut self, depth: u32, f: V<'t>, a: V<'t>) -> V<'t> {\n        v44_note(1, f);\n",
        "V44_APPLY_ANCHOR_MISSING",
    ),
    (
        "    pub(crate) fn do_proj(&mut self, depth: u32, ty_name: NamePtr<'t>, idx: u16, v: V<'t>) -> V<'t> {\n",
        "    pub(crate) fn do_proj(&mut self, depth: u32, ty_name: NamePtr<'t>, idx: u16, v: V<'t>) -> V<'t> {\n        v44_note(2, v);\n",
        "V44_PROJ_ANCHOR_MISSING",
    ),
    (
        "    fn unfold_value_go(&mut self, depth: u32, v: V<'t>, force: bool) -> V<'t> {\n",
        "    fn unfold_value_go(&mut self, depth: u32, v: V<'t>, force: bool) -> V<'t> {\n        v44_note(3, v);\n",
        "V44_UNFOLD_ANCHOR_MISSING",
    ),
    (
        "    pub(crate) fn iota_value(&mut self, depth: u32, v: V<'t>) -> Option<V<'t>> {\n",
        "    pub(crate) fn iota_value(&mut self, depth: u32, v: V<'t>) -> Option<V<'t>> {\n        v44_note(4, v);\n",
        "V44_IOTA_ANCHOR_MISSING",
    ),
    (
        "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n",
        "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        V44_FORCE_CALLS.fetch_add(1, Relaxed);\n",
        "V44_FORCE_ANCHOR_MISSING",
    ),
]

for old, new, err in anchors:
    if old not in s:
        raise SystemExit(err)
    s = s.replace(old, new, 1)

p.write_text(s)

p = Path("src/tc.rs")
s = p.read_text()
old = (
    "    pub fn check_all_declars(&self) {\n"
    "        if self.config.num_threads > 1 {\n"
    "            self.check_all_declars_par(self.config.num_threads)\n"
    "        } else {\n"
    "            self.check_all_declars_serial()\n"
    "        }\n"
    "    }"
)
new = (
    "    pub fn check_all_declars(&self) {\n"
    "        if self.config.num_threads > 1 {\n"
    "            self.check_all_declars_par(self.config.num_threads)\n"
    "        } else {\n"
    "            self.check_all_declars_serial()\n"
    "        }\n"
    "        crate::eval::v44_transfer_report();\n"
    "    }"
)
if old not in s:
    raise SystemExit("V44_REPORT_ANCHOR_MISSING")
s = s.replace(old, new, 1)
p.write_text(s)

print("V44_BLIND_RESIDUAL_CENSUS_INSTALLED")
