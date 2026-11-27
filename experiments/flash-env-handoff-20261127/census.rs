//! Observation-only counters, excluded from every production speed comparison.
use std::cell::RefCell;
use std::collections::{BTreeMap, HashSet};
#[derive(Default)]
struct Census { counts: BTreeMap<&'static str,u64>, cold: HashSet<(u32,u64)> }
thread_local! { static STATS: RefCell<Census> = RefCell::new(Census::default()); }
pub(crate) fn inc(name: &'static str) { STATS.with(|s| *s.borrow_mut().counts.entry(name).or_default()+=1); }
pub(crate) fn cold(e:u32,mask:u64) {
    STATS.with(|s| {let mut s=s.borrow_mut(); let repeated=!s.cold.insert((e,mask));
        *s.counts.entry("cold_projections").or_default()+=1;
        if repeated {*s.counts.entry("repeated_cold_exact_key").or_default()+=1;}
    });
}
pub(crate) fn frame(full:bool,slots:u32) {
    STATS.with(|s| {let mut s=s.borrow_mut();
        *s.counts.entry(if full {"full_prefix_selections"} else {"sparse_selections"}).or_default()+=1;
        *s.counts.entry(if full {"full_prefix_slots"} else {"sparse_slots"}).or_default()+=u64::from(slots);
    });
}
pub(crate) fn epoch() { STATS.with(|s| {let mut s=s.borrow_mut();s.cold.clear();*s.counts.entry("value_epochs").or_default()+=1;}); }
pub(crate) fn finish() { STATS.with(|s| {let mut s=s.borrow_mut();eprintln!("HANDOFF_CENSUS {}",serde_json::to_string(&s.counts).unwrap());s.counts.clear();s.cold.clear();}); }
