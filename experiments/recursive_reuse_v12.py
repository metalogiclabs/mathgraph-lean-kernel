#!/usr/bin/env python3
from pathlib import Path
import argparse

SITE='''        for p in params.iter().take(num_params).copied() {
            match self.force_all(depth, cur) {
                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => panic!("ran out of param telescope in projection"),
            }
        }'''

V11='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } if depth == 5 && flag == Check && idx == 2 => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),
                    _ => panic!("ran out of param telescope in projection"),
                },
            }
        }'''

CANDS=[
 ('depth_gt_0','depth > 0'),
 ('check_mode','flag == Check'),
 ('idx_zero','idx == 0'),
 ('idx_nonzero','idx > 0'),
 ('depth_eq_8_idx0','depth == 8 && idx == 0'),
 ('depth_eq_4_idx0','depth == 4 && idx == 0'),
]

def install_v11(s):
    if V11 in s: return s
    if SITE not in s: raise SystemExit('projection site missing')
    return s.replace(SITE,V11,1)

def add_candidate(s, cond):
    marker='''                _ => match self.force_all(depth, cur) {
                    Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),'''
    repl=f'''                Value::Pi {{ domain, body, .. }} if {cond} => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {{
                    Value::Pi {{ domain, body, .. }} => cur = self.apply_closure(depth, body, p, Some(*domain)),'''
    if marker not in s: raise SystemExit('V11 residual branch missing')
    return s.replace(marker,repl,1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--candidate',type=int); ap.add_argument('--list',action='store_true')
    a=ap.parse_args(); p=Path(a.repo)/'src/infer.rs'; s=install_v11(p.read_text())
    print('PARENT_STATE=V11_variant_5')
    print('INSTALLED_V11_GUARD=depth==5&&flag==Check&&idx==2')
    print(f'REUSE_CANDIDATES={len(CANDS)}')
    for i,(n,c) in enumerate(CANDS): print(f'CAND_{i}={n};guard={c}')
    if a.candidate is not None:
        n,c=CANDS[a.candidate]; s=add_candidate(s,c); p.write_text(s)
        print(f'APPLIED_CANDIDATE={a.candidate}'); print(f'APPLIED_NAME={n}'); print('RECURSIVE_REUSE_EDIT=1')
    elif not a.list:
        p.write_text(s); print('V11_BASELINE_ONLY=1')
if __name__=='__main__': main()
