from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()

anchor = "use std::cell::OnceCell;\n"
insert = r'''use std::sync::atomic::{AtomicU64, Ordering};

static PRUNE_CALLS: AtomicU64 = AtomicU64::new(0);
static PRUNE_POP_SUM: AtomicU64 = AtomicU64::new(0);
static PRUNE_HIGH_SUM: AtomicU64 = AtomicU64::new(0);
static PRUNE_CONS_STEPS: AtomicU64 = AtomicU64::new(0);
static PRUNE_SELECTED: AtomicU64 = AtomicU64::new(0);
static PRUNE_FRAMED_TAILS: AtomicU64 = AtomicU64::new(0);
static PRUNE_POP_LE1: AtomicU64 = AtomicU64::new(0);
static PRUNE_POP_LE2: AtomicU64 = AtomicU64::new(0);
static PRUNE_POP_LE4: AtomicU64 = AtomicU64::new(0);
static PRUNE_POP_LE8: AtomicU64 = AtomicU64::new(0);
static PRUNE_HIGH_GE16: AtomicU64 = AtomicU64::new(0);
static PRUNE_HIGH_GE32: AtomicU64 = AtomicU64::new(0);
static PRUNE_HIGH_GE48: AtomicU64 = AtomicU64::new(0);

pub fn print_prune_mask_census() {
    eprintln!(
        "PRUNE_MASK_CENSUS calls={} pop_sum={} high_sum={} cons_steps={} selected={} framed_tails={} pop_le1={} pop_le2={} pop_le4={} pop_le8={} high_ge16={} high_ge32={} high_ge48={}",
        PRUNE_CALLS.load(Ordering::Relaxed),
        PRUNE_POP_SUM.load(Ordering::Relaxed),
        PRUNE_HIGH_SUM.load(Ordering::Relaxed),
        PRUNE_CONS_STEPS.load(Ordering::Relaxed),
        PRUNE_SELECTED.load(Ordering::Relaxed),
        PRUNE_FRAMED_TAILS.load(Ordering::Relaxed),
        PRUNE_POP_LE1.load(Ordering::Relaxed),
        PRUNE_POP_LE2.load(Ordering::Relaxed),
        PRUNE_POP_LE4.load(Ordering::Relaxed),
        PRUNE_POP_LE8.load(Ordering::Relaxed),
        PRUNE_HIGH_GE16.load(Ordering::Relaxed),
        PRUNE_HIGH_GE32.load(Ordering::Relaxed),
        PRUNE_HIGH_GE48.load(Ordering::Relaxed),
    );
}
'''
assert anchor in s
s = s.replace(anchor, anchor + insert, 1)

fn_anchor = "    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {\n"
fn_insert = r'''        let pop = u64::from(mask.count_ones());
        let high = u64::from(64 - mask.leading_zeros());
        PRUNE_CALLS.fetch_add(1, Ordering::Relaxed);
        PRUNE_POP_SUM.fetch_add(pop, Ordering::Relaxed);
        PRUNE_HIGH_SUM.fetch_add(high, Ordering::Relaxed);
        if pop <= 1 { PRUNE_POP_LE1.fetch_add(1, Ordering::Relaxed); }
        if pop <= 2 { PRUNE_POP_LE2.fetch_add(1, Ordering::Relaxed); }
        if pop <= 4 { PRUNE_POP_LE4.fetch_add(1, Ordering::Relaxed); }
        if pop <= 8 { PRUNE_POP_LE8.fetch_add(1, Ordering::Relaxed); }
        if high >= 16 { PRUNE_HIGH_GE16.fetch_add(1, Ordering::Relaxed); }
        if high >= 32 { PRUNE_HIGH_GE32.fetch_add(1, Ordering::Relaxed); }
        if high >= 48 { PRUNE_HIGH_GE48.fetch_add(1, Ordering::Relaxed); }
        let mut census_cons_steps = 0u64;
        let mut census_selected = 0u64;
'''
assert fn_anchor in s
s = s.replace(fn_anchor, fn_anchor + fn_insert, 1)

framed_anchor = "                value::Env::Framed { mask: fmask, slots, .. } => {\n"
assert framed_anchor in s
s = s.replace(framed_anchor, framed_anchor + "                    PRUNE_FRAMED_TAILS.fetch_add(1, Ordering::Relaxed);\n", 1)

cons_anchor = "                value::Env::Cons { v, parent, .. } => {\n"
cons_insert = "                    census_cons_steps += 1;\n"
assert cons_anchor in s
s = s.replace(cons_anchor, cons_anchor + cons_insert, 1)

sel_anchor = "                    if rem & 1 != 0 {\n"
assert sel_anchor in s
s = s.replace(sel_anchor, sel_anchor + "                        census_selected += 1;\n", 1)

end_anchor = "        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };\n"
end_insert = "        PRUNE_CONS_STEPS.fetch_add(census_cons_steps, Ordering::Relaxed);\n        PRUNE_SELECTED.fetch_add(census_selected, Ordering::Relaxed);\n"
assert end_anchor in s
s = s.replace(end_anchor, end_insert + end_anchor, 1)

p.write_text(s)

m = Path('src/main.rs')
ms = m.read_text()
main_anchor = "    export_file.check_all_declars();\n"
assert main_anchor in ms
ms = ms.replace(main_anchor, main_anchor + "    sokonanoda::eval::print_prune_mask_census();\n", 1)
m.write_text(ms)

print('applied prune-env mask census v4')
