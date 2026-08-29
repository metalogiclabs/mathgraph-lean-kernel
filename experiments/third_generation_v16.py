#!/usr/bin/env python3
from pathlib import Path
import argparse

V11_OLD='''        for p in params.iter().take(num_params).copied() {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }'''
V11_NEW='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } if depth == 5 && flag == Check && idx == 2 => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''
ENSURE_OLD='''        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }'''
ENSURE_NEW='''        match v {
            Value::Sort { level , .. } => *level,
            _ => match self.force_all(depth, v) {
                Value::Sort { level , .. } => *level,
                _ => panic!("expected a sort"),
            },
        }'''
APP_OLD='''            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!("expected a pi type"),
            };'''
APP_NEW='''            let (domain, body) = match fty {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => {
                    let fty_f = self.force_all(depth, fty);
                    match fty_f {
                        Value::Pi { domain, body, .. } => (*domain, body),
                        _ => panic!("expected a pi type"),
                    }
                }
            };'''
PRIOR_OLD='''        for i in 0..idx {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => {'''
PRIOR_NEW='''        for i in 0..idx {
            match cur {
                Value::Pi { domain, body, .. } => {'''

# Residual-derived from remaining force_all -> demanded-constructor sites after V15 winner.
CANDIDATES=[
('struct_type_direct_rigid',
'''        let struct_ty_f = self.force_all(depth, struct_ty);''',
'''        let struct_ty_f = match struct_ty {
            Value::Rigid { .. } => struct_ty,
            _ => self.force_all(depth, struct_ty),
        };'''),
('final_field_direct_pi',
'''        match self.force_all(depth, cur) {
            Value::Pi { domain, .. } => {''',
'''        match cur {
            Value::Pi { domain, .. } => {'''),
('param_telescope_direct_pi_fallback',
V11_NEW,
'''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }''')]

def repl(s,old,new,name):
    if old not in s: raise SystemExit(f'missing site: {name}')
    return s.replace(old,new,1)

def install_common(s):
    s=repl(s,V11_OLD,V11_NEW,'V11')
    s=repl(s,ENSURE_OLD,ENSURE_NEW,'ensure')
    s=repl(s,APP_OLD,APP_NEW,'app')
    return s

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--state',choices=['ablate','parent'],required=True); ap.add_argument('--variant',type=int); ap.add_argument('--list',action='store_true'); a=ap.parse_args()
    p=Path(a.repo)/'src/infer.rs'; s=install_common(p.read_text())
    if a.state=='parent': s=repl(s,PRIOR_OLD,PRIOR_NEW,'V15_prior_field')
    print(f'STATE={a.state}')
    print('PARENT=V11+ensure+app+V15_prior' if a.state=='parent' else 'PARENT=V11+ensure+app;V15_ABLATED=1')
    print('RESIDUAL_SOURCE=V15_remaining_force_all_constructor_demands')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    print(f'GENERATED_CANDIDATES={len(CANDIDATES)}')
    for i,(n,_,_) in enumerate(CANDIDATES): print(f'CANDIDATE_{i}={n}')
    if a.variant is not None:
        n,old,new=CANDIDATES[a.variant]; s=repl(s,old,new,n); print(f'APPLIED_VARIANT={a.variant}:{n}')
    elif not a.list: print('BASELINE_ONLY=1')
    p.write_text(s)
if __name__=='__main__': main()

# V16 trigger: third-generation causal gate.
