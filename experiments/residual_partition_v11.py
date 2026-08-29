#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, collections, re

# V11: derive a finer context partition from the V10 near-miss site.
# Probe records only local program state (depth, InferFlag, projection idx).
# Generated patches never see corpus identity.

def frozen_prefix(s: str) -> str:
    legacy_g1='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }'''
    g1='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        if let Value::Sort { level, .. } = v { return *level; }
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }'''
    if legacy_g1 in s: s=s.replace(legacy_g1,g1,1)
    elif 'pub(crate) fn ensure_sort_v' not in s or 'if let Value::Sort' not in s:
        raise SystemExit('frozen g1 semantic transition missing')
    legacy_g2='''        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!("expected a pi type"),
            };'''
    g2='''        while let Some(arg) = args.pop() {
            let (domain, body) = match fty {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => {
                    let fty_f = self.force_all(depth, fty);
                    match fty_f {
                        Value::Pi { domain, body, .. } => (*domain, body),
                        _ => panic!("expected a pi type"),
                    }
                }
            };'''
    if legacy_g2 in s: s=s.replace(legacy_g2,g2,1)
    elif 'while let Some(arg) = args.pop()' not in s or 'match fty {' not in s:
        raise SystemExit('frozen g2 semantic transition missing')
    return s

SITE = '''        for p in params.iter().take(num_params).copied() {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }'''

def probe_source(s: str) -> str:
    if SITE not in s: raise SystemExit('V11 target site missing')
    repl='''        for p in params.iter().take(num_params).copied() {
            let __v11_flag: u8 = if flag == Check { 0 } else { 1 };
            eprintln!("V11CTX depth={} flag={} idx={}", depth, __v11_flag, idx);
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }'''
    return s.replace(SITE,repl,1)

def guarded_source(s: str, cond: str) -> str:
    if SITE not in s: raise SystemExit('V11 target site missing')
    repl=f'''        for p in params.iter().take(num_params).copied() {{
            match cur {{
                Value::Pi {{ domain, body, .. }} if {cond} => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {{
                    Value::Pi {{ domain, body, .. }} => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                }},
            }}
        }}'''
    return s.replace(SITE,repl,1)

def parse_trace(path: Path):
    c=collections.Counter()
    rx=re.compile(r'V11CTX depth=(\d+) flag=(\d+) idx=(\d+)')
    for line in path.read_text(errors='ignore').splitlines():
        m=rx.search(line)
        if m: c[tuple(map(int,m.groups()))]+=1
    return c

def choose_cells(std: collections.Counter, cedar: collections.Counter, cap=12):
    keys=set(std)|set(cedar)
    ts=sum(std.values()) or 1; tc=sum(cedar.values()) or 1
    rows=[]
    for k in keys:
        ps=std[k]/ts; pc=cedar[k]/tc
        # Prefer observed, distribution-distinguishing cells. No outcome/corpus id is embedded in patch.
        score=abs(ps-pc) + 0.05*(ps+pc)
        rows.append((score,k,std[k],cedar[k]))
    rows.sort(reverse=True)
    return rows[:cap]

def cond_of(k):
    d,f,i=k
    return f'depth == {d} && flag == {"Check" if f==0 else "InferOnly"} && idx == {i}'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('repo')
    ap.add_argument('--probe',action='store_true')
    ap.add_argument('--std-trace',type=Path)
    ap.add_argument('--cedar-trace',type=Path)
    ap.add_argument('--variant',type=int)
    ap.add_argument('--list',action='store_true')
    a=ap.parse_args(); p=Path(a.repo)/'src/infer.rs'; s=frozen_prefix(p.read_text())
    if a.probe:
        p.write_text(probe_source(s)); print('V11_PROBE=1'); return
    if not a.std_trace or not a.cedar_trace: raise SystemExit('traces required unless --probe')
    rows=choose_cells(parse_trace(a.std_trace),parse_trace(a.cedar_trace))
    print('RESIDUAL_SOURCE=V10_depth_gt_0_near_miss')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    print(f'DERIVED_PARTITION_CELLS={len(rows)}')
    for j,(score,k,ns,nc) in enumerate(rows):
        print(f'CELL_{j}=depth={k[0]};flag={k[1]};idx={k[2]};std_n={ns};cedar_n={nc};guard={cond_of(k)}')
    if a.variant is not None:
        if a.variant<0 or a.variant>=len(rows): raise SystemExit('variant out of range')
        cond=cond_of(rows[a.variant][1]); p.write_text(guarded_source(s,cond))
        print(f'APPLIED_VARIANT={a.variant}'); print(f'APPLIED_GUARD={cond}'); print('EXECUTABLE_RESIDUAL_PARTITION=1')
    elif not a.list:
        p.write_text(s); print('FROZEN_PREFIX_ONLY=1')

if __name__=='__main__': main()
