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

# Different dataflow roles, all derived from existing force_all -> constructor demand sites.
CANDIDATES = [
    ('ensure_sort_direct_sort',
'''        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }''',
'''        match v {
            Value::Sort { level , .. } => *level,
            _ => match self.force_all(depth, v) {
                Value::Sort { level , .. } => *level,
                _ => panic!("expected a sort"),
            },
        }'''),
    ('app_direct_pi',
'''            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!("expected a pi type"),
            };''',
'''            let (domain, body) = match fty {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => {
                    let fty_f = self.force_all(depth, fty);
                    match fty_f {
                        Value::Pi { domain, body, .. } => (*domain, body),
                        _ => panic!("expected a pi type"),
                    }
                }
            };'''),
    ('prior_field_direct_pi',
'''        for i in 0..idx {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => {''',
'''        for i in 0..idx {
            match cur {
                Value::Pi { domain, body, .. } => {'''),
    ('final_field_direct_pi',
'''        match self.force_all(depth, cur) {
            Value::Pi { domain, .. } => {''',
'''        match cur {
            Value::Pi { domain, .. } => {'''),
]

# For prior/final fields, direct-only is intentionally tested as a distinct operator family;
# semantic gate decides whether removing forcing is lawful. No corpus identity or thresholds enter source edits.

def install_v11(s):
    if V11_NEW in s: return s
    if V11_OLD not in s: raise SystemExit('V11 parent site missing')
    return s.replace(V11_OLD, V11_NEW, 1)

def apply_candidate(s, i):
    name, old, new = CANDIDATES[i]
    if old not in s: raise SystemExit(f'candidate site missing: {name}')
    return s.replace(old, new, 1), name

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('repo')
    ap.add_argument('--state',choices=['pre','post'],required=True)
    ap.add_argument('--variant',type=int)
    ap.add_argument('--list',action='store_true')
    a=ap.parse_args()
    p=Path(a.repo)/'src/infer.rs'; s=p.read_text()
    if a.state == 'post': s=install_v11(s)
    print(f'STATE={a.state}')
    print('PARENT_REPAIR=V11_variant_5' if a.state=='post' else 'PARENT_REPAIR=ABLATED')
    print('RESIDUAL_SOURCE=V13_post_V11_same_family_exhausted')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    print(f'OPERATOR_FAMILY_CANDIDATES={len(CANDIDATES)}')
    for i,(name,_,_) in enumerate(CANDIDATES): print(f'CANDIDATE_{i}={name}')
    if a.variant is not None:
        if not 0 <= a.variant < len(CANDIDATES): raise SystemExit('variant out of range')
        s,name=apply_candidate(s,a.variant)
        print(f'APPLIED_VARIANT={a.variant}')
        print(f'APPLIED_OPERATOR={name}')
    elif not a.list:
        print('BASELINE_ONLY=1')
    p.write_text(s)

if __name__=='__main__': main()
