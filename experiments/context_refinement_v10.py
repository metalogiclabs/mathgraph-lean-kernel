#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, re

# V10 takes the V9 veto as evidence that the constructor-fastpath abstraction is
# too coarse. It refines only by context variables already available at the
# discovered site; no corpus identity is visible to generated code.

def frozen_prefix(s: str) -> str:
    legacy_g1='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    g1='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    if legacy_g1 in s:
        s=s.replace(legacy_g1,g1,1)
    elif 'pub(crate) fn ensure_sort_v' not in s or 'if let Value::Sort' not in s:
        raise SystemExit('frozen g1 semantic transition missing')

    legacy_g2='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
    g2='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
    if legacy_g2 in s:
        s=s.replace(legacy_g2,g2,1)
    elif 'while let Some(arg) = args.pop()' not in s or 'match fty {' not in s:
        raise SystemExit('frozen g2 semantic transition missing')
    return s

PAT = re.compile(
    r'(?P<indent>^[ \t]*)match self\\.force_all\\(depth, (?P<var>[A-Za-z_][A-Za-z0-9_]*)\\) \\{\\n'
    r'(?P=indent)    Value::(?P<ctor>[A-Za-z_][A-Za-z0-9_]*) (?P<pat>\\{[^\\n]*\\}) => (?P<body>[^\\n]+),',
    re.M,
)

def candidates(s: str):
    return [(m, s.count('\n',0,m.start())+1) for m in PAT.finditer(s)]

def enclosing_fn(s: str, pos: int) -> str:
    hits=list(re.finditer(r'^[ \t]*(?:pub\\(crate\\) )?fn ([A-Za-z_][A-Za-z0-9_]*)\\s*\\(', s[:pos], re.M))
    return hits[-1].group(1) if hits else 'unknown'

def variants(s: str):
    out=[]
    for i,(m,line) in enumerate(candidates(s)):
        fn=enclosing_fn(s,m.start()); var=m.group('var'); ctor=m.group('ctor')
        # Smallest lexical distinctions available at each discovered residual site.
        if 'depth' in s[max(0,m.start()-1500):m.start()+200]:
            out += [(i,'depth_eq_0','depth == 0'),(i,'depth_gt_0','depth > 0')]
        if fn == 'infer_proj_v':
            out += [(i,'check_mode','flag == Check'),(i,'infer_only_mode','flag == InferOnly'),
                    (i,'projection_zero','idx == 0'),(i,'projection_nonzero','idx > 0')]
    # de-duplicate while preserving order
    seen=set(); ans=[]
    for x in out:
        if x not in seen: seen.add(x); ans.append(x)
    return ans

def rewrite_guarded(s: str, cand_idx: int, cond: str) -> tuple[str,str]:
    cs=candidates(s)
    m,line=cs[cand_idx]
    ind=m.group('indent'); var=m.group('var'); ctor=m.group('ctor'); pat=m.group('pat'); body=m.group('body')
    start=m.start(); first_end=m.end()
    close_pat=re.compile(r'^'+re.escape(ind)+r'\\}', re.M)
    cm=close_pat.search(s, first_end)
    if not cm: raise SystemExit('could not locate match close')
    tail=s[first_end:cm.start()]
    replacement=(
        f"{ind}match {var} {{\\n"
        f"{ind}    Value::{ctor} {pat} if {cond} => {body},\\n"
        f"{ind}    _ => match self.force_all(depth, {var}) {{\\n"
        f"{ind}        Value::{ctor} {pat} => {body},"
        + tail + f"{ind}    }},\\n{ind}}}"
    )
    return s[:start]+replacement+s[cm.end():], f'line={line};var={var};ctor={ctor};guard={cond}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--variant',type=int); ap.add_argument('--list',action='store_true')
    a=ap.parse_args(); p=Path(a.repo)/'src/infer.rs'; s=frozen_prefix(p.read_text())
    vs=variants(s)
    print('RESIDUAL_SOURCE=V9_cross_corpus_economic_veto')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    print(f'CONTEXT_VARIANTS={len(vs)}')
    for j,(ci,name,cond) in enumerate(vs): print(f'VARIANT_{j}=candidate={ci};name={name};guard={cond}')
    if a.variant is not None:
        ci,name,cond=vs[a.variant]; s,ident=rewrite_guarded(s,ci,cond); p.write_text(s)
        print(f'APPLIED_VARIANT={a.variant}'); print(f'APPLIED_NAME={name}'); print(f'APPLIED_IDENTITY={ident}'); print('EXECUTABLE_CONTEXT_REFINEMENT=1')
    elif not a.list:
        p.write_text(s); print('FROZEN_PREFIX_ONLY=1')

if __name__=='__main__': main()
