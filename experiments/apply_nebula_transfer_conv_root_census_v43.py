from pathlib import Path

p = Path("src/conv.rs")
s = p.read_text()

import_anchor = "use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
if import_anchor not in s:
    raise SystemExit("V43_CONV_IMPORT_ANCHOR_MISSING")
s = s.replace(
    import_anchor,
    import_anchor
    + "use std::collections::BTreeMap;\n"
    + "use std::sync::{Mutex, OnceLock};\n",
    1,
)

type_anchor = "fn rigid_head_eq<'a>(hx: RigidHead<'a>, hy: RigidHead<'a>) -> bool {\n"
if type_anchor not in s:
    raise SystemExit("V43_CONV_TYPE_ANCHOR_MISSING")

instrumentation = r"""
type V43RootPairMap = BTreeMap<(u8, u8), u64>;
static V43_TRANSFER_ROOT_PAIRS: OnceLock<Mutex<V43RootPairMap>> = OnceLock::new();

#[inline]
fn v43_value_kind(v: &Value<'_>) -> u8 {
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
fn v43_kind_name(k: u8) -> &'static str {
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
fn v43_transfer_record(a: &Value<'_>, b: &Value<'_>) {
    let key = (v43_value_kind(a), v43_value_kind(b));
    let map = V43_TRANSFER_ROOT_PAIRS.get_or_init(|| Mutex::new(BTreeMap::new()));
    let mut map = map.lock().unwrap();
    *map.entry(key).or_insert(0) += 1;
}

pub(crate) fn v43_transfer_report(force_calls: u64) {
    let map = V43_TRANSFER_ROOT_PAIRS.get_or_init(|| Mutex::new(BTreeMap::new()));
    let map = map.lock().unwrap();
    let total: u64 = map.values().copied().sum();
    let mut rows: Vec<_> = map.iter().map(|(&(a, b), &n)| (a, b, n)).collect();
    rows.sort_by_key(|&(a, b, n)| (std::cmp::Reverse(n), a, b));
    eprintln!(
        "V43_TRANSFER force_calls={} conv_calls={} root_pairs={}",
        force_calls,
        total,
        rows.len()
    );
    if let Some((a, b, n)) = rows.first().copied() {
        let share = if total == 0 { 0.0 } else { 100.0 * n as f64 / total as f64 };
        eprintln!(
            "V43_TRANSFER_DOMINANT lhs={} rhs={} calls={} call_share={:.6}%",
            v43_kind_name(a),
            v43_kind_name(b),
            n,
            share
        );
    }
    eprintln!("V43_TRANSFER_RULE=instrumentation_only_exact_replay_required");
}

"""
s = s.replace(type_anchor, instrumentation + type_anchor, 1)

old_conv = (
    "    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {\n"
    "        self.unbudgeted(|s| s.unify::<true>(depth, a, b))\n"
    "    }\n"
)
new_conv = (
    "    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {\n"
    "        v43_transfer_record(a, b);\n"
    "        self.unbudgeted(|s| s.unify::<true>(depth, a, b))\n"
    "    }\n"
)
if old_conv not in s:
    raise SystemExit("V43_CONV_TYPES_ANCHOR_MISSING")
s = s.replace(old_conv, new_conv, 1)
p.write_text(s)

p = Path("src/eval.rs")
s = p.read_text()
import_anchor = "use std::cell::OnceCell;\n"
if import_anchor not in s:
    raise SystemExit("V43_EVAL_IMPORT_ANCHOR_MISSING")
s = s.replace(
    import_anchor,
    import_anchor + "use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n",
    1,
)

type_anchor = "pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;\n"
if type_anchor not in s:
    raise SystemExit("V43_EVAL_TYPE_ANCHOR_MISSING")
s = s.replace(
    type_anchor,
    type_anchor
    + "\nstatic V43_TRANSFER_FORCE_CALLS: AtomicU64 = AtomicU64::new(0);\n\n"
    + "#[inline]\n"
    + "pub(crate) fn v43_transfer_force_calls() -> u64 {\n"
    + "    V43_TRANSFER_FORCE_CALLS.load(Relaxed)\n"
    + "}\n",
    1,
)

force_anchor = "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n"
if force_anchor not in s:
    raise SystemExit("V43_FORCE_ANCHOR_MISSING")
s = s.replace(
    force_anchor,
    force_anchor + "        V43_TRANSFER_FORCE_CALLS.fetch_add(1, Relaxed);\n",
    1,
)
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
    "        crate::conv::v43_transfer_report(crate::eval::v43_transfer_force_calls());\n"
    "    }"
)
if old not in s:
    raise SystemExit("V43_REPORT_ANCHOR_MISSING")
s = s.replace(old, new, 1)
p.write_text(s)

print("V43_TRANSFER_CONV_ROOT_CENSUS_INSTALLED")
