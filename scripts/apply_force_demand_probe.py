#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
evalp = root / 'src' / 'eval.rs'
convp = root / 'src' / 'conv.rs'
s = evalp.read_text()
c = convp.read_text()

# Diagnostic-only probe. Tag every known force_all demand site and classify
# whether the input is already terminal/stable (output pointer unchanged).
anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::sync::atomic::{AtomicU64, Ordering};

const MG_FORCE_TAGS: usize = 16;
static MG_FORCE_CALLS: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_SAME: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_PI: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_LAM: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_RIGID: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_UNFOLD: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_THUNK: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_OTHER: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];

#[inline]
fn mg_add(a: &[AtomicU64; MG_FORCE_TAGS], tag: usize) { a[tag].fetch_add(1, Ordering::Relaxed); }

pub fn report_force_demand_stats() {
    if std::env::var_os("MATHGRAPH_FORCE_DEMAND_PROBE").is_none() { return; }
    for tag in 0..MG_FORCE_TAGS {
        let calls = MG_FORCE_CALLS[tag].load(Ordering::Relaxed);
        if calls == 0 { continue; }
        eprintln!(
            "MATHGRAPH_FORCE tag={} calls={} same={} pi={} lam={} rigid={} unfold={} thunk={} other={}",
            tag,
            calls,
            MG_FORCE_SAME[tag].load(Ordering::Relaxed),
            MG_FORCE_PI[tag].load(Ordering::Relaxed),
            MG_FORCE_LAM[tag].load(Ordering::Relaxed),
            MG_FORCE_RIGID[tag].load(Ordering::Relaxed),
            MG_FORCE_UNFOLD[tag].load(Ordering::Relaxed),
            MG_FORCE_THUNK[tag].load(Ordering::Relaxed),
            MG_FORCE_OTHER[tag].load(Ordering::Relaxed),
        );
    }
}
'''
assert anchor in s
s = s.replace(anchor, anchor + insert, 1)

# Add a tagged wrapper. Tag 0 is reserved for unclassified/external demand.
needle = "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n"
wrapper = r'''    #[inline]
    pub(crate) fn force_all_tag(&mut self, tag: usize, depth: u32, v: V<'t>) -> V<'t> {
        mg_add(&MG_FORCE_CALLS, tag);
        match v {
            Value::Pi { .. } => mg_add(&MG_FORCE_PI, tag),
            Value::Lam { .. } => mg_add(&MG_FORCE_LAM, tag),
            Value::Rigid { .. } => mg_add(&MG_FORCE_RIGID, tag),
            Value::Unfold { .. } => mg_add(&MG_FORCE_UNFOLD, tag),
            Value::Thunk { .. } => mg_add(&MG_FORCE_THUNK, tag),
            _ => mg_add(&MG_FORCE_OTHER, tag),
        }
        let r = self.force_all(depth, v);
        if std::ptr::eq(r, v) { mg_add(&MG_FORCE_SAME, tag); }
        r
    }

'''
assert needle in s
s = s.replace(needle, wrapper + needle, 1)

# eval.rs call-site tags. Keep force_all's own definition untouched.
repls = [
    ('let cur_f = self.force_all(binder_depth, cur);', 'let cur_f = self.force_all_tag(1, binder_depth, cur);'),
    ('let ty_f = self.force_all(depth, ty);', 'let ty_f = self.force_all_tag(2, depth, ty);'),
    ('let struct_ty = self.force_all(depth, struct_ty);', 'let struct_ty = self.force_all_tag(3, depth, struct_ty);'),
    ('let cf = self.force_all(depth, cur);', 'let cf = self.force_all_tag(4, depth, cur);'),
    ('let major_ty_f = self.force_all(depth, major_ty);', 'let major_ty_f = self.force_all_tag(5, depth, major_ty);'),
    ('let qmk = self.force_all(depth, *args.get(qmk_pos)?);', 'let qmk = self.force_all_tag(6, depth, *args.get(qmk_pos)?);'),
    ('let f = self.force_all(depth, v);', 'let f = self.force_all_tag(7, depth, v);'),
]
for old,new in repls:
    if old in s:
        s = s.replace(old,new)

# conv.rs sites get distinct tags.
crepls = [
    ('let ty_f = self.force_all(depth, ty);', 'let ty_f = self.force_all_tag(8, depth, ty);'),
    ('let cod_f = self.force_all(depth + 1, cod);', 'let cod_f = self.force_all_tag(9, depth + 1, cod);'),
    ('let t_f = self.force_all(depth, t);', 'let t_f = self.force_all_tag(10, depth, t);'),
    ('let ty_f = self.force_all(depth, t);', 'let ty_f = self.force_all_tag(11, depth, t);'),
]
for old,new in crepls:
    if old in c:
        c = c.replace(old,new)

evalp.write_text(s)
convp.write_text(c)

m = root / 'src' / 'main.rs'
t = m.read_text()
anchor = '    match out {\n'
replacement = '    sokonanoda::eval::report_force_demand_stats();\n    match out {\n'
assert anchor in t
if replacement not in t:
    t = t.replace(anchor, replacement, 1)
m.write_text(t)
print('force demand probe applied')
