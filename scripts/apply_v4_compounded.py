#!/usr/bin/env python3
from pathlib import Path
import argparse
p=argparse.ArgumentParser(); p.add_argument('path', nargs='?', default='src/infer.rs'); p.add_argument('--only', action='append', default=[]); a=p.parse_args()
s=Path(a.path).read_text()
repls=[
('ensure_sort_direct_sort','''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''','''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),
('app_direct_pi','''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''','''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''),
('param_telescope_direct_pi_fallback','''        for p in params.iter().take(num_params).copied() {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }''','''        for p in params.iter().take(num_params).copied() {\n            match cur {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => match self.force_all(depth, cur) {\n                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                    _ => panic!("ran out of param telescope in projection"),\n                },\n            }\n        }'''),
('prior_field_direct_pi','''        for i in 0..idx {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => {''','''        for i in 0..idx {\n            match cur {\n                Value::Pi { domain, body, .. } => {''')]
sel=set(a.only)
for n,o,r in repls:
    if sel and n not in sel: continue
    c=s.count(o)
    if c!=1: raise SystemExit(f'{n}: expected 1 site, found {c}')
    s=s.replace(o,r,1); print('APPLIED='+n)
Path(a.path).write_text(s)
