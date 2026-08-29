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
FINAL_OLD='''        match self.force_all(depth, cur) {
            Value::Pi { domain, .. } => {'''
FINAL_NEW='''        match cur {
            Value::Pi { domain, .. } => {'''

SUPPORTS=[('ensure', [('ensure_sort_direct_sort',ENSURE_OLD,ENSURE_NEW)]),
          ('app', [('app_direct_pi',APP_OLD,APP_NEW)]),
          ('ensure_app', [('ensure_sort_direct_sort',ENSURE_OLD,ENSURE_NEW),('app_direct_pi',APP_OLD,APP_NEW)])]
TARGETS=[('prior_field_direct_pi',PRIOR_OLD,PRIOR_NEW),('final_field_direct_pi',FINAL_OLD,FINAL_NEW)]

def repl(s,old,new,name):
    if old not in s: raise SystemExit(f'missing site: {name}')
    return s.replace(old,new,1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--state',choices=['pre','post'],required=True); ap.add_argument('--support',type=int,required=True); ap.add_argument('--target',type=int); a=ap.parse_args()
    p=Path(a.repo)/'src/infer.rs'; s=p.read_text()
    if a.state=='post': s=repl(s,V11_OLD,V11_NEW,'V11')
    sn,ops=SUPPORTS[a.support]
    for name,old,new in ops: s=repl(s,old,new,name)
    print(f'STATE={a.state}'); print(f'SUPPORT={a.support}:{sn}'); print('PARENT_REPAIR=V11_variant_5' if a.state=='post' else 'PARENT_REPAIR=ABLATED'); print('RESIDUAL_SOURCE=V14_state_dependent_portal_closure'); print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    if a.target is None: print('SUPPORT_BASELINE=1')
    else:
        name,old,new=TARGETS[a.target]; s=repl(s,old,new,name); print(f'TARGET={a.target}:{name}')
    p.write_text(s)

if __name__=='__main__': main()
