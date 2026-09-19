#!/usr/bin/env python3
from pathlib import Path

p=Path("src/tc.rs")
c=p.read_text()
old="""        let base = bumpalo::Bump::new();
        let mut session_cache = crate::util::SessionCache::new(&base);
        let mut sbump = crate::util::SessionBump::new();
        let mut pending = Some(first);
        loop {
"""
new="""        let base = bumpalo::Bump::new();
        let mut session_cache = crate::util::SessionCache::new(&base);
        let mut sbump = crate::util::SessionBump::new();
        let mut pending = Some(first);
        let qckn_decl_census = std::env::var_os("QCKN_DECL_CENSUS").is_some();
        let mut qckn_rows: Vec<(usize, u64, u8, u128)> = Vec::new();
        loop {
"""
if c.count(old)!=1: raise SystemExit(f"prologue anchor count={c.count(old)}")
c=c.replace(old,new,1)

old="""                while i < end {
                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");
                    i += 1;
                    self.check_declar_with(tctx, cache, sbump.get(), d);
                    if sbump.allocated_bytes() > SESSION_BUDGET {
"""
new="""                while i < end {
                    let idx = i;
                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");
                    let name_hash = d.info().name.get_hash();
                    let kind: u8 = match d {
                        Declar::Axiom { .. } => 0,
                        Declar::Quot { .. } => 1,
                        Declar::Theorem { .. } => 2,
                        Declar::Definition { .. } => 3,
                        Declar::Opaque { .. } => 4,
                        Declar::Inductive(..) => 5,
                        Declar::Constructor(..) => 6,
                        Declar::Recursor(..) => 7,
                    };
                    i += 1;
                    let started = qckn_decl_census.then(std::time::Instant::now);
                    self.check_declar_with(tctx, cache, sbump.get(), d);
                    if let Some(started) = started {
                        qckn_rows.push((idx, name_hash, kind, started.elapsed().as_nanos()));
                    }
                    if sbump.allocated_bytes() > SESSION_BUDGET {
"""
if c.count(old)!=1: raise SystemExit(f"loop anchor count={c.count(old)}")
c=c.replace(old,new,1)

old="""            if finished {
                return
            }
"""
new="""            if finished {
                if qckn_decl_census {
                    let thread = std::thread::current();
                    let thread_name = thread.name().unwrap_or("serial");
                    let mut out = String::with_capacity(qckn_rows.len().saturating_mul(48));
                    for (idx, name_hash, kind, ns) in &qckn_rows {
                        use std::fmt::Write as _;
                        let _ = writeln!(&mut out, "QCKN_DECL\t{}\t{}\t{}\t{}\t{}", thread_name, idx, name_hash, kind, ns);
                    }
                    eprint!("{}", out);
                }
                return
            }
"""
if c.count(old)!=1: raise SystemExit(f"finish anchor count={c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)
print("QCKN_DECL_CENSUS_PATCH=PASS")
