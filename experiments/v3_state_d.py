#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib

ENSURE_OLD='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }'''
ENSURE_NEW='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {
        if let Value::Sort { level, .. } = v { return *level; }
        match self.force_all(depth, v) {
            Value::Sort { level , .. } => *level,
            _ => panic!("expected a sort"),
        }
    }'''
APP_OLD='''        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!("expected a pi type"),
            };'''
APP_NEW='''        while let Some(arg) = args.pop() {
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
PARAM_OLD='''        for p in params.iter().take(num_params).copied() {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }'''
PARAM_V11='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } if depth == 5 && flag == Check && idx == 2 => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''
PARAM_FULL='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''
PRIOR_OLD='''        for i in 0..idx {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => {'''
PRIOR_NEW='''        for i in 0..idx {
            match cur {
                Value::Pi { domain, body, .. } => {'''

def one(s, old, new, name):
    if old not in s: raise SystemExit(f'missing site: {name}')
    return s.replace(old,new,1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); a=ap.parse_args()
    p=Path(a.repo)/'src/infer.rs'; s=p.read_text()
    s=one(s,ENSURE_OLD,ENSURE_NEW,'G1 ensure')
    s=one(s,APP_OLD,APP_NEW,'G2 app')
    s=one(s,PARAM_OLD,PARAM_V11,'V11 residual repair')
    s=one(s,PRIOR_OLD,PRIOR_NEW,'V15 prior_field')
    s=one(s,PARAM_V11,PARAM_FULL,'V16 param_telescope')
    p.write_text(s)
    print('V3_LINEAGE=G1+G2+V11+prior_field+param_telescope')
    print('V17_LINEAGE_CERTIFICATE_REQUIRED=1')
    print('SOURCE_SHA256='+hashlib.sha256(s.encode()).hexdigest())

if __name__=='__main__': main()
