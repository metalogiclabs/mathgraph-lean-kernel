#!/usr/bin/env python3
from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else "src/infer.rs")
s = p.read_text()

repls = [
("ensure_sort_direct_sort", '''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }''', '''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        if let Value::Sort { level, .. } = v { return *level; }
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }'''),
("app_direct_pi", '''        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!("expected a pi type"),
            };''', '''        while let Some(arg) = args.pop() {
            let (domain, body) = match fty {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => {
                    let fty_f = self.force_all(depth, fty);
                    match fty_f {
                        Value::Pi { domain, body, .. } => (*domain, body),
                        _ => panic!("expected a pi type"),
                    }
                }
            };'''),
("param_telescope_direct_pi_fallback", '''        for p in params.iter().take(num_params).copied() {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }''', '''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''),
("prior_field_direct_pi", '''        for i in 0..idx {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => {''', '''        for i in 0..idx {
            match cur {
                Value::Pi { domain, body, .. } => {'''),
]

for name, old, new in repls:
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{name}: expected exactly one source site, found {n}")
    s = s.replace(old, new, 1)
    print(f"APPLIED={name}")

p.write_text(s)
print("MSI_COMPOUNDED_V3=1")
print("LINEAGE=V17_state_D")
