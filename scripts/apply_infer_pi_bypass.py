#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src'/'infer.rs'
s=p.read_text()
old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {'''
new='''        while let Some(arg) = args.pop() {\n            let fty_f = match fty {\n                Value::Pi { .. } => fty,\n                _ => self.force_all(depth, fty),\n            };\n            let (domain, body) = match fty_f {'''
assert old in s
p.write_text(s.replace(old,new,1))
print('applied infer_app_v Pi-demand bypass')
