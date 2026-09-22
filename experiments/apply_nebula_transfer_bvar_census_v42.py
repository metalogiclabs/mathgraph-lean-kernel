from pathlib import Path

p = Path("src/eval.rs")
s = p.read_text()

import_anchor = "use std::cell::OnceCell;\n"
if import_anchor not in s:
    raise SystemExit("V42_IMPORT_ANCHOR_MISSING")
s = s.replace(
    import_anchor,
    import_anchor
    + "use std::collections::HashMap;\n"
    + "use std::sync::{Mutex, OnceLock};\n"
    + "use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n",
    1,
)

type_anchor = "pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;\n"
if type_anchor not in s:
    raise SystemExit("V42_TYPE_ANCHOR_MISSING")

instrumentation = r'''
type V42TransferOriginMap = HashMap<(&'static str, u32), (u64, u64, u64)>;
static V42_TRANSFER_ORIGINS: OnceLock<Mutex<V42TransferOriginMap>> = OnceLock::new();
static V42_TRANSFER_FORCE_CALLS: AtomicU64 = AtomicU64::new(0);

#[inline]
fn v42_transfer_origins() -> &'static Mutex<V42TransferOriginMap> {
    V42_TRANSFER_ORIGINS.get_or_init(|| Mutex::new(HashMap::new()))
}

#[inline]
fn v42_transfer_record(file: &'static str, line: u32, hit: bool) {
    let mut m = v42_transfer_origins().lock().unwrap();
    let e = m.entry((file, line)).or_insert((0, 0, 0));
    e.0 += 1;
    if hit { e.1 += 1; } else { e.2 += 1; }
}

pub(crate) fn v42_transfer_report() {
    let force = V42_TRANSFER_FORCE_CALLS.load(Relaxed);
    let m = v42_transfer_origins().lock().unwrap();
    let mut rows: Vec<_> = m
        .iter()
        .map(|(&(f, l), &(c, h, n))| (f, l, c, h, n))
        .collect();
    rows.sort_by_key(|r| (std::cmp::Reverse(r.4), r.0, r.1));
    let calls: u64 = rows.iter().map(|r| r.2).sum();
    let hits: u64 = rows.iter().map(|r| r.3).sum();
    let news: u64 = rows.iter().map(|r| r.4).sum();
    eprintln!(
        "V42_TRANSFER force_calls={} bvar_calls={} hits={} news={} sites={}",
        force, calls, hits, news, rows.len()
    );
    if let Some((file, line, calls, hits, news)) = rows.first().copied() {
        let share = if rows.iter().map(|r| r.4).sum::<u64>() == 0 {
            0.0
        } else {
            100.0 * news as f64 / rows.iter().map(|r| r.4).sum::<u64>() as f64
        };
        eprintln!(
            "V42_TRANSFER_DOMINANT file={} line={} calls={} hits={} news={} new_share={:.6}%",
            file, line, calls, hits, news, share
        );
    }
    eprintln!("V42_TRANSFER_RULE=instrumentation_only_exact_replay_required");
}
'''
s = s.replace(type_anchor, type_anchor + instrumentation + "\n", 1)

old_bvar = """    #[inline]
    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            return v;
        }
        let empty = self.empty_spine();
        let v = value::mk_bvar_with_empty(self.arena, level, ty, empty);
        self.tc_cache.bvar_hc.insert(key, v);
        v
    }"""
new_bvar = """    #[inline]
    #[track_caller]
    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        let loc = std::panic::Location::caller();
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            v42_transfer_record(loc.file(), loc.line(), true);
            return v;
        }
        let empty = self.empty_spine();
        let v = value::mk_bvar_with_empty(self.arena, level, ty, empty);
        self.tc_cache.bvar_hc.insert(key, v);
        v42_transfer_record(loc.file(), loc.line(), false);
        v
    }"""
if old_bvar not in s:
    raise SystemExit("V42_BVAR_ANCHOR_MISSING")
s = s.replace(old_bvar, new_bvar, 1)

force_anchor = """    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
"""
if force_anchor not in s:
    raise SystemExit("V42_FORCE_ANCHOR_MISSING")
s = s.replace(
    force_anchor,
    force_anchor + "        V42_TRANSFER_FORCE_CALLS.fetch_add(1, Relaxed);\n",
    1,
)

p.write_text(s)

p = Path("src/tc.rs")
s = p.read_text()
old = """    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
    }"""
new = """    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
        crate::eval::v42_transfer_report();
    }"""
if old not in s:
    raise SystemExit("V42_REPORT_ANCHOR_MISSING")
s = s.replace(old, new, 1)
p.write_text(s)

print("V42_TRANSFER_BVAR_CENSUS_INSTALLED")
