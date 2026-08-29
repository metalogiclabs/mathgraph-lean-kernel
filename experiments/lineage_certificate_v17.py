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
PRIOR_OLD='''        for i in 0..idx {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => {'''
PRIOR_NEW='''        for i in 0..idx {
            match cur {
                Value::Pi { domain, body, .. } => {'''
PARAM_FULL='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''

def repl(s, old, new, name):
    if old not in s:
        raise SystemExit(f'missing site: {name}')
    return s.replace(old,new,1)

def support(s):
    return repl(repl(s,ENSURE_OLD,ENSURE_NEW,'ensure/G1'),APP_OLD,APP_NEW,'app/G2')

def make(s,state):
    s=support(s)
    if state in {'B','C','F','D'}:
        s=repl(s,V11_OLD,V11_NEW,'V11')
    if state in {'E','C','D'}:
        s=repl(s,PRIOR_OLD,PRIOR_NEW,'prior_field')
    if state in {'F','D'}:
        s=repl(s,V11_NEW,PARAM_FULL,'param_telescope')
    return s

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--state',choices=list('ABCEFD'),required=True); a=ap.parse_args()
    p=Path(a.repo)/'src/infer.rs'; s=make(p.read_text(),a.state); p.write_text(s)
    h=hashlib.sha256(s.encode()).hexdigest()
    desc={
      'A':'G1+G2 support; V11 absent; prior absent',
      'B':'G1+G2+V11',
      'E':'G1+G2+prior; V11 absent',
      'C':'G1+G2+V11+prior (V15 parent)',
      'F':'G1+G2+V11+param; prior ablated',
      'D':'G1+G2+V11+prior+param (V16 child)',
    }[a.state]
    print(f'STATE={a.state}')
    print(f'DESCRIPTION={desc}')
    print(f'SOURCE_SHA256={h}')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')

if __name__=='__main__': main()
