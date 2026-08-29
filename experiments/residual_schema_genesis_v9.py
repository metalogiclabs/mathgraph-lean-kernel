#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, re

# V9 freezes the transformation schema before the external tournament runs.

def frozen_prefix(s: str) -> str:
    old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    if old not in s: raise SystemExit('frozen g1 site missing')
    s=s.replace(old,new,1)
    old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
    new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
    if old not in s: raise SystemExit('frozen g2 site missing')
    return s.replace(old,new,1)

# Generic source-derived schema. No portal names or hand-picked line numbers.
PAT = re.compile(
    r'(?P<indent>^[ \t]*)match self\.force_all\(depth, (?P<var>[A-Za-z_][A-Za-z0-9_]*)\) \{\n'
    r'(?P=indent)    Value::(?P<ctor>[A-Za-z_][A-Za-z0-9_]*) (?P<pat>\{[^\n]*\}) => (?P<body>[^\n]+),',
    re.M,
)

def candidates(s: str):
    out=[]
    for m in PAT.finditer(s):
        line=s.count('\n',0,m.start())+1
        out.append((m,line))
    return out

def rewrite_one(s: str, idx: int) -> tuple[str,str]:
    cs=candidates(s)
    if idx < 0 or idx >= len(cs): raise SystemExit(f'candidate index {idx} out of range 0..{len(cs)-1}')
    m,line=cs[idx]
    ind=m.group('indent'); var=m.group('var'); ctor=m.group('ctor'); pat=m.group('pat'); body=m.group('body')
    replacement=(
        f"{ind}match {var} {{\n"
        f"{ind}    Value::{ctor} {pat} => {body},\n"
        f"{ind}    _ => match self.force_all(depth, {var}) {{\n"
        f"{ind}        Value::{ctor} {pat} => {body},"
    )
    start=m.start(); first_end=m.end()
    close_pat=re.compile(r'^'+re.escape(ind)+r'\}', re.M)
    cm=close_pat.search(s, first_end)
    if not cm: raise SystemExit('could not locate match close')
    tail=s[first_end:cm.start()]
    newblock=replacement+tail+f"{ind}    }},\n{ind}}}"
    s2=s[:start]+newblock+s[cm.end():]
    ident=f'line={line};var={var};ctor={ctor}'
    return s2,ident

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('repo')
    ap.add_argument('--candidate',type=int)
    ap.add_argument('--list',action='store_true')
    args=ap.parse_args()
    repo=Path(args.repo); p=repo/'src/infer.rs'
    s=frozen_prefix(p.read_text())
    cs=candidates(s)
    print('GENERATED_SCHEMA=constructor_fastpath_over_force_residual')
    print('PORTAL_LABELS_USED=0')
    print(f'DISCOVERED_CANDIDATES={len(cs)}')
    for i,(m,line) in enumerate(cs):
        print(f'CANDIDATE_{i}=line={line};var={m.group("var")};ctor={m.group("ctor")}')
    if args.candidate is not None:
        s,ident=rewrite_one(s,args.candidate)
        p.write_text(s)
        print(f'APPLIED_CANDIDATE={args.candidate}')
        print(f'APPLIED_IDENTITY={ident}')
        print('EXECUTABLE_SOURCE_EDIT=1')
    elif not args.list:
        p.write_text(s)
        print('FROZEN_PREFIX_ONLY=1')

if __name__=='__main__': main()
