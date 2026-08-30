#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
np=root/'src/name.rs'; s=np.read_text()
needle='''impl<'x, 't: 'x, 'p: 't> TcCtx<'t, 'p> {\n'''
insert='''impl<'x, 't: 'x, 'p: 't> TcCtx<'t, 'p> {\n    pub(crate) fn name_to_string_v4(&self, n: NamePtr<'t>) -> String {\n        match self.read_name(n) {\n            Name::Anon => String::new(),\n            Name::Str(pfx, sfx, ..) => {\n                let p = self.name_to_string_v4(pfx);\n                let s = self.read_string(sfx);\n                if p.is_empty() { s.to_string() } else { format!("{}.{}", p, s) }\n            }\n            Name::Num(pfx, k, ..) => {\n                let p = self.name_to_string_v4(pfx);\n                if p.is_empty() { k.to_string() } else { format!("{}.{}", p, k) }\n            }\n        }\n    }\n'''
if s.count(needle)!=1: raise SystemExit('name impl site mismatch')
s=s.replace(needle,insert,1); np.write_text(s)

tp=root/'src/tc.rs'; s=tp.read_text()
old='''                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");\n                    i += 1;\n                    self.check_declar_with(tctx, cache, sbump.get(), d);\n'''
new='''                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");\n                    let decl_idx = i;\n                    i += 1;\n                    let probe_name = tctx.name_to_string_v4(d.info().name);\n                    if probe_name.ends_with("denote_blastDivSubtractShift_q") {\n                        let probe_t0 = std::time::Instant::now();\n                        self.check_declar_with(tctx, cache, sbump.get(), d);\n                        eprintln!("V4_TARGET_DECL index={} name={} nanos={}", decl_idx, probe_name, probe_t0.elapsed().as_nanos());\n                    } else {\n                        self.check_declar_with(tctx, cache, sbump.get(), d);\n                    }\n'''
if s.count(old)!=1: raise SystemExit('tc declaration loop site mismatch')
s=s.replace(old,new,1); tp.write_text(s)
print('V4_TARGET_PROBE=APPLIED')
