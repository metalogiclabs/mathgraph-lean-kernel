#!/usr/bin/env python3
from pathlib import Path
import re, sys, json

root = Path(sys.argv[1])
src = root / 'src'
entries = []
tag = 0
pat = re.compile(r'\b(self|tc)\.force_all\(')

for p in sorted(src.glob('*.rs')):
    text = p.read_text()
    out = []
    pos = 0
    for m in pat.finditer(text):
        # Skip the method definition area accidentally matching generated code (none expected).
        line = text.count('\n', 0, m.start()) + 1
        tag += 1
        entries.append({'tag': tag, 'file': p.name, 'line': line, 'receiver': m.group(1)})
        out.append(text[pos:m.start()])
        out.append(f'{m.group(1)}.force_all_tag({tag}, ')
        pos = m.end()
    if entries and pos:
        out.append(text[pos:])
        p.write_text(''.join(out))

if tag == 0:
    raise SystemExit('no force_all call sites found')

# Inject tagged wrapper + counters immediately before force_all definition in eval.rs.
p = src / 'eval.rs'
s = p.read_text()
needle = "    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {"
assert needle in s
helper = r'''    #[inline(never)]
    pub(crate) fn force_all_tag(&mut self, tag: usize, depth: u32, v: V<'t>) -> V<'t> {
        use std::sync::atomic::{AtomicU64, Ordering};
        static TOTAL: AtomicU64 = AtomicU64::new(0);
        static COUNTS: [AtomicU64; 128] = [const { AtomicU64::new(0) }; 128];
        static PI_COUNTS: [AtomicU64; 128] = [const { AtomicU64::new(0) }; 128];
        let n = COUNTS[tag].fetch_add(1, Ordering::Relaxed) + 1;
        TOTAL.fetch_add(1, Ordering::Relaxed);
        if matches!(v, Value::Pi { .. }) {
            PI_COUNTS[tag].fetch_add(1, Ordering::Relaxed);
        }
        if n <= 8 || n % 1000000 == 0 {
            let pn = PI_COUNTS[tag].load(Ordering::Relaxed);
            eprintln!("FORCE_ORIGIN tag={} count={} pi={}", tag, n, pn);
        }
        self.force_all(depth, v)
    }

'''
s = s.replace(needle, helper + needle, 1)
p.write_text(s)

(root / 'force_origin_manifest.json').write_text(json.dumps(entries, indent=2))
print(json.dumps({'sites': tag, 'entries': entries}, indent=2))
