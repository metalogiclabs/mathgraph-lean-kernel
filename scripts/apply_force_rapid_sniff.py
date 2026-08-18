#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else 'probe'
p = root / 'src' / 'eval.rs'
s = p.read_text()

if mode == 'no_lookup':
    old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }\n        let mut cur = v;'''
    new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        let mut cur = v;'''
    assert old in s
    p.write_text(s.replace(old, new, 1))
    print('rapid sniff: removed force_all store_lookup only')
    raise SystemExit

if mode == 'no_note':
    old = '        self.note_whnf(depth, v, result, steps);\n        result\n    }\n\n    fn iota_step'
    new = '        let _ = steps;\n        result\n    }\n\n    fn iota_step'
    assert old in s
    p.write_text(s.replace(old, new, 1))
    print('rapid sniff: removed force_all note_whnf only')
    raise SystemExit

assert mode == 'probe'
convp = root / 'src' / 'conv.rs'
c = convp.read_text()

# Exhaustively tag every static self.force_all call site in eval.rs and conv.rs.
tagmap = []
tag = 1
def tag_calls(text, filename):
    global tag
    out=[]
    for lineno,line in enumerate(text.splitlines(True),1):
        if 'self.force_all(' in line:
            while 'self.force_all(' in line:
                this = tag
                line = line.replace('self.force_all(', f'self.force_all_tag({this}, ', 1)
                tagmap.append((this, filename, lineno, line.strip()))
                tag += 1
        out.append(line)
    return ''.join(out)

s = tag_calls(s, 'src/eval.rs')
c = tag_calls(c, 'src/conv.rs')
assert tag < 256, tag

anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::sync::atomic::{AtomicU64, Ordering};

const MG_FORCE_TAGS: usize = 256;
static MG_FORCE_CALLS: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_FORCE_SAME: [AtomicU64; MG_FORCE_TAGS] = [const { AtomicU64::new(0) }; MG_FORCE_TAGS];
static MG_ALL_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_ALL_ZERO: AtomicU64 = AtomicU64::new(0);
static MG_ALL_SAME: AtomicU64 = AtomicU64::new(0);
static MG_ALL_STORE_HITS: AtomicU64 = AtomicU64::new(0);
static MG_ALL_PI: AtomicU64 = AtomicU64::new(0);
static MG_ALL_LAM: AtomicU64 = AtomicU64::new(0);
static MG_ALL_RIGID: AtomicU64 = AtomicU64::new(0);
static MG_ALL_UNFOLD: AtomicU64 = AtomicU64::new(0);
static MG_ALL_THUNK: AtomicU64 = AtomicU64::new(0);
static MG_ALL_OTHER: AtomicU64 = AtomicU64::new(0);

#[inline] fn mg_inc(a: &AtomicU64) { a.fetch_add(1, Ordering::Relaxed); }

pub fn report_force_rapid_stats() {
    if std::env::var_os("MATHGRAPH_FORCE_RAPID_PROBE").is_none() { return; }
    eprintln!("MATHGRAPH_FORCE_ALL calls={} zero={} same={} store_hits={} pi={} lam={} rigid={} unfold={} thunk={} other={}",
        MG_ALL_CALLS.load(Ordering::Relaxed), MG_ALL_ZERO.load(Ordering::Relaxed),
        MG_ALL_SAME.load(Ordering::Relaxed), MG_ALL_STORE_HITS.load(Ordering::Relaxed),
        MG_ALL_PI.load(Ordering::Relaxed), MG_ALL_LAM.load(Ordering::Relaxed),
        MG_ALL_RIGID.load(Ordering::Relaxed), MG_ALL_UNFOLD.load(Ordering::Relaxed),
        MG_ALL_THUNK.load(Ordering::Relaxed), MG_ALL_OTHER.load(Ordering::Relaxed));
    for tag in 1..MG_FORCE_TAGS {
        let calls = MG_FORCE_CALLS[tag].load(Ordering::Relaxed);
        if calls != 0 {
            eprintln!("MATHGRAPH_FORCE_SITE tag={} calls={} same={}", tag, calls, MG_FORCE_SAME[tag].load(Ordering::Relaxed));
        }
    }
}
'''
assert anchor in s
s = s.replace(anchor, anchor + insert, 1)

needle = "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n"
wrapper = r'''    #[inline]
    pub(crate) fn force_all_tag(&mut self, tag: usize, depth: u32, v: V<'t>) -> V<'t> {
        MG_FORCE_CALLS[tag].fetch_add(1, Ordering::Relaxed);
        let r = self.force_all(depth, v);
        if std::ptr::eq(r, v) { MG_FORCE_SAME[tag].fetch_add(1, Ordering::Relaxed); }
        r
    }

'''
assert needle in s
s = s.replace(needle, wrapper + needle, 1)

# Count all force_all entries, input kinds, store hits, zero-step exits, and same-pointer exits.
old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }\n        let mut cur = v;\n        let mut steps = 0u32;'''
new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        mg_inc(&MG_ALL_CALLS);\n        match v {\n            Value::Pi { .. } => mg_inc(&MG_ALL_PI),\n            Value::Lam { .. } => mg_inc(&MG_ALL_LAM),\n            Value::Rigid { .. } => mg_inc(&MG_ALL_RIGID),\n            Value::Unfold { .. } => mg_inc(&MG_ALL_UNFOLD),\n            Value::Thunk { .. } => mg_inc(&MG_ALL_THUNK),\n            _ => mg_inc(&MG_ALL_OTHER),\n        }\n        if let Some(r) = self.store_lookup(depth, v) {\n            mg_inc(&MG_ALL_STORE_HITS);\n            if std::ptr::eq(r, v) { mg_inc(&MG_ALL_SAME); }\n            return r;\n        }\n        let mut cur = v;\n        let mut steps = 0u32;'''
assert old in s
s = s.replace(old, new, 1)
old2 = '''        self.note_whnf(depth, v, result, steps);\n        result\n    }\n\n    fn iota_step'''
new2 = '''        if steps == 0 { mg_inc(&MG_ALL_ZERO); }\n        if std::ptr::eq(result, v) { mg_inc(&MG_ALL_SAME); }\n        self.note_whnf(depth, v, result, steps);\n        result\n    }\n\n    fn iota_step'''
assert old2 in s
s = s.replace(old2, new2, 1)

p.write_text(s)
convp.write_text(c)
(root/'MATHGRAPH_FORCE_TAGMAP.txt').write_text('\n'.join(f'{t}\t{f}:{ln}\t{txt}' for t,f,ln,txt in tagmap)+'\n')

m = root / 'src' / 'main.rs'
t = m.read_text()
anchor = '    match out {\n'
replacement = '    sokonanoda::eval::report_force_rapid_stats();\n    match out {\n'
assert anchor in t
if replacement not in t:
    t = t.replace(anchor, replacement, 1)
m.write_text(t)
print(f'rapid force probe applied with {len(tagmap)} tagged call sites')
