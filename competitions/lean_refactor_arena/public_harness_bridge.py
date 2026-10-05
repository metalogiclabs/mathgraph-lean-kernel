#!/usr/bin/env python3
"""Inject one candidate into a cloned public Lean Refactor Arena work file.

This adapter deliberately delegates compilation and scoring to the public
aurasoph/lean-refactor harness. It changes only the target declaration after
arena.py prepare has materialized the benchmark context.
"""
from __future__ import annotations
import argparse, json, re, subprocess
from pathlib import Path

def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")

def read_candidate(path: Path, name: str, label: str | None) -> str:
    matches=[]
    for i,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line)
        if row.get("name")!=name: continue
        if label is not None and row.get("label")!=label: continue
        proof=str(row.get("proof") or "")
        if not proof: raise SystemExit(f"{path}:{i}: empty proof")
        matches.append(proof)
    if len(matches)!=1:
        raise SystemExit(f"expected exactly one candidate for {name!r} label={label!r}, got {len(matches)}")
    return matches[0]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--competition",required=True)
    ap.add_argument("--project",required=True)
    ap.add_argument("--name",required=True)
    ap.add_argument("--candidate",required=True)
    ap.add_argument("--label")
    args=ap.parse_args()
    comp=Path(args.competition).resolve()
    rows=[json.loads(x) for x in (comp/"benchmark_data_warmup.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    row=next((r for r in rows if r["name"]==args.name),None)
    if row is None: raise SystemExit(f"benchmark theorem not found: {args.name}")
    candidate=read_candidate(Path(args.candidate),args.name,args.label)
    subprocess.run(["python3","arena.py","prepare","--name",args.name,"--force"],cwd=comp,check=True)
    work=comp/"projects"/args.project/"Arena"/f"{slug(args.name)}.lean"
    if not work.is_file(): raise SystemExit(f"prepared work file missing: {work}")
    text=work.read_text(encoding="utf-8")
    frozen=str(row["src"])
    if text.count(frozen)!=1:
        raise SystemExit(f"frozen declaration occurs {text.count(frozen)} times in {work}; expected 1")
    work.write_text(text.replace(frozen,candidate,1),encoding="utf-8")
    print(json.dumps({"schema":"mathgraph.lra.public-harness-injection.v1","name":args.name,"project":args.project,"work_file":str(work),"candidate_bytes":len(candidate.encode("utf-8"))},indent=2))
    print("VERIFIED_PUBLIC_HARNESS_CANDIDATE_INJECTED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
