#!/usr/bin/env python3
"""Bounded source-derived observation acquisition; emits candidates, never warrants.

No theorem-specific sites, observer lists, or equality names are inputs. The
finite grammar is human supplied. This acquires representations of witnesses
already present in source, not new mathematical lemmas. Lean remains the oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

RULE_VERSION='source-observation-v1'
def digest(s): return hashlib.sha256(s.encode()).hexdigest()

def observer_at(text, start):
    """Read the explicit parenthesized observer, conservatively, without a parser."""
    if start >= len(text) or text[start] != '(': return None
    depth=0
    for end in range(start,len(text)):
        if text[end]=='(': depth+=1
        elif text[end]==')':
            depth-=1
            if depth==0: return text[start:end+1],end+1
    return None

def discover(row, limit=24):
    source=row['proof']
    if ':= by' not in source or re.search(r'\b(sorry|admit|axiom)\b|--|/\*|/\-|"',source): return []
    header=source.split(':= by',1)[0]
    out=[];seen={digest(source)}
    def emit(proof,operator,site):
        sha=digest(proof)
        if sha in seen or len(out)>=limit: return
        if proof.split(':= by',1)[0]!=header: raise ValueError('statement mutation')
        seen.add(sha)
        out.append({'name':row['name'],'label':operator+'_'+sha[:12],
            'proof':proof,'proof_sha256':sha,'parent_sha256':digest(source),
            'operator':operator,'rule_version':RULE_VERSION,'discovered':site,
            'status':'CANDIDATE_UNVERIFIED'})
    # Infer the observer from Lean's expected equality rather than naming one.
    for match in re.finditer(r'\bcongrArg +',source):
        obs=observer_at(source,match.end())
        if obs:
            term,end=obs
            emit(source[:match.end()]+'_'+source[end:], 'infer_observer',
                 {'observer':term,'offset':match.start()})
    # Acquire an equality/observer/normalizer triple directly from a terminal
    # local observation block. Exact indentation and end-of-block guard scope.
    pattern=re.compile(r'(?m)^( +)have (\w+) := (congrArg [^\n]+)\n')
    for match in pattern.finditer(source):
        indent,name,expr=match.groups();pos=match.end();rules=[]
        while True:
            rw=re.match(re.escape(indent)+r'rw \[([\s\S]*?)\] at '+re.escape(name)+r'\n',source[pos:])
            if not rw: break
            # Do not swallow another tactic or a nested rw list.
            body=rw.group(1)
            if '\n'+indent+'rw ' in body or '[' in body or ']' in body: break
            rules.append(body);pos+=rw.end()
        terminal=re.match(re.escape(indent)+r'exact '+re.escape(name)+r'(?:\n|$)',source[pos:])
        if not rules or not terminal: continue
        end=pos+terminal.end()
        following=source[end:]
        first=following.splitlines()[0] if following else ''
        if first.strip() and len(first)-len(first.lstrip())>=len(indent): continue
        obs=re.match(r'congrArg +',expr);parsed=observer_at(expr,obs.end())
        if not parsed: continue
        term,oe=parsed;witness=expr[oe:].strip()
        if not re.fullmatch(r'\w+(?:\.symm)?',witness): continue
        site={'observer':term,'witness':witness,'normalizers':rules,'offset':match.start()}
        for tactic,operator in [('simpa only','fuse_observation_only'),('simpa','fuse_observation_simp')]:
            replacement=indent+tactic+' ['+', '.join(rules)+'] using '+expr+'\n'
            emit(source[:match.start()]+replacement+source[end:],operator,site)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--portfolio',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--name',action='append');args=ap.parse_args()
    rows=[json.loads(x) for x in Path(args.portfolio).read_text().splitlines() if x.strip()]
    bank=[]
    for row in rows:
        if args.name and row['name'] not in args.name: continue
        bank.append({'name':row['name'],'proof':row['proof'],'label':'v16_control','parent_sha256':digest(row['proof']),'operator':'control'})
        bank.extend(discover(row))
    Path(args.out).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in bank))
    print(json.dumps({'rule_version':RULE_VERSION,'rows':len(bank),'candidates':sum(x['operator']!='control' for x in bank),'bank_sha256':digest(Path(args.out).read_text())}))
if __name__=='__main__':main()
