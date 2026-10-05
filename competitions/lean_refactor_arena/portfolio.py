#!/usr/bin/env python3
"""Merge verified Lean Refactor Arena candidate artifacts into one portfolio.

Inputs are JSONL files with {name, proof}. Duplicate theorem names fail closed.
This tool does not decide verification status; callers should pass only
candidates that have already crossed their authority boundary.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

def read(path: Path):
    out=[]
    for i,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line)
        name=str(row.get("name") or "")
        proof=str(row.get("proof") or "")
        if not name or not proof:
            raise SystemExit(f"{path}:{i}: expected name and proof")
        out.append({"name":name,"proof":proof})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",action="append",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    merged={}
    origins={}
    for raw in args.input:
        p=Path(raw)
        for row in read(p):
            n=row["name"]
            if n in merged:
                raise SystemExit(f"duplicate candidate {n}: {origins[n]} and {p}")
            merged[n]=row["proof"]; origins[n]=str(p)
    out=Path(args.out)
    with out.open("w",encoding="utf-8") as f:
        for n in sorted(merged):
            f.write(json.dumps({"name":n,"proof":merged[n]},ensure_ascii=False)+"\n")
    print(json.dumps({"schema":"mathgraph.lean-refactor-arena.portfolio.v1","count":len(merged),"names":sorted(merged),"origins":origins},indent=2))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
