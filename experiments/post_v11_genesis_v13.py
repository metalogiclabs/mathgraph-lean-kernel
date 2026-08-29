#!/usr/bin/env python3
from pathlib import Path
import argparse, collections, re

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

def install_v11(s):
    if V11 in s: return s
    if SITE not in s: raise SystemExit('projection site missing')
    return s.replace(SITE,V11,1)

def probe_source(s):
    s=install_v11(s)
    old='''        for p in params.iter().take(num_params).copied() {
            match cur {'''
    new='''        for (j, p) in params.iter().take(num_params).copied().enumerate() {
            let __v13_flag: u8 = if flag == Check { 0 } else { 1 };
            let __v13_is_pi: u8 = if matches!(cur, Value::Pi { .. }) { 1 } else { 0 };
            eprintln!("V13CTX depth={} flag={} idx={} num_params={} j={} is_pi={}", depth, __v13_flag, idx, num_params, j, __v13_is_pi);
            match cur {'''
    if old not in s: raise SystemExit('V11 loop site missing')
    return s.replace(old,new,1)

def parse(path):
    c=collections.Counter(); rx=re.compile(r'V13CTX depth=(\d+) flag=(\d+) idx=(\d+) num_params=(\d+) j=(\d+) is_pi=(\d+)')
    for line in path.read_text(errors='ignore').splitlines():
        m=rx.search(line)
        if m: c[tuple(map(int,m.groups()))]+=1
    return c

def choose(std,cedar,cap=16):
    keys=set(std)|set(cedar); ts=sum(std.values()) or 1; tc=sum(cedar.values()) or 1; rows=[]
    for k in keys:
        ps=std[k]/ts; pc=cedar[k]/tc
        if k[-1] != 1: continue
        score=abs(ps-pc)+0.05*(ps+pc)
        rows.append((score,k,std[k],cedar[k]))
    rows.sort(reverse=True)
    return rows[:cap]

def cond(k):
    d,f,i,np,j,ispi=k
    return f'depth == {d} && flag == {"Check" if f==0 else "InferOnly"} && idx == {i} && num_params == {np} && j == {j}'

def patch(s,c):
    s=install_v11(s)
    old='''        for p in params.iter().take(num_params).copied() {
            match cur {
                Value::Pi { domain, body, .. } if depth == 5 && flag == Check && idx == 2 => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {'''
    new=f'''        for (j, p) in params.iter().take(num_params).copied().enumerate() {{
            match cur {{
                Value::Pi {{ domain, body, .. }} if depth == 5 && flag == Check && idx == 2 => cur = self.apply_closure(depth, body, p, Some(*domain)),
                Value::Pi {{ domain, body, .. }} if {c} => cur = self.apply_closure(depth, body, p, Some(*domain)),
                _ => match self.force_all(depth, cur) {{'''
    if old not in s: raise SystemExit('V11 installed site missing')
    return s.replace(old,new,1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--probe',action='store_true'); ap.add_argument('--std-trace',type=Path); ap.add_argument('--cedar-trace',type=Path); ap.add_argument('--variant',type=int); ap.add_argument('--list',action='store_true')
    a=ap.parse_args(); p=Path(a.repo)/'src/infer.rs'; s=p.read_text()
    if a.probe:
        p.write_text(probe_source(s)); print('V13_PROBE=1'); return
    if not a.std_trace or not a.cedar_trace: raise SystemExit('traces required')
    rows=choose(parse(a.std_trace),parse(a.cedar_trace))
    print('PARENT_STATE=V11_variant_5')
    print('RESIDUAL_SOURCE=V12_no_old_candidate_newly_admissible')
    print('CORPUS_ID_VISIBLE_TO_PATCH=0')
    print(f'DERIVED_POST_V11_CELLS={len(rows)}')
    for n,(score,k,ns,nc) in enumerate(rows): print(f'CELL_{n}=depth={k[0]};flag={k[1]};idx={k[2]};num_params={k[3]};j={k[4]};std_n={ns};cedar_n={nc};guard={cond(k)}')
    if a.variant is not None:
        if not 0 <= a.variant < len(rows): raise SystemExit('variant out of range')
        c=cond(rows[a.variant][1]); p.write_text(patch(s,c)); print(f'APPLIED_VARIANT={a.variant}'); print(f'APPLIED_GUARD={c}'); print('POST_V11_GENERATED_EDIT=1')
    elif not a.list:
        p.write_text(install_v11(s)); print('V11_BASELINE_ONLY=1')
if __name__=='__main__': main()

# workflow trigger: V13 post-V11 genesis
