#!/usr/bin/env python3
import re, sys
from collections import defaultdict
from pathlib import Path

RE = re.compile(
    r"V118_RESULT tag=(\S+) test=(\S+) threshold=(\S+) rc=(\d+) wall=([0-9.]+) rss_kb=(\d+) user=([0-9.]+) sys=([0-9.]+)"
)

rows=[]
for path in map(Path, sys.argv[1:]):
    for line in path.read_text(errors="replace").splitlines():
        m=RE.search(line)
        if not m: continue
        tag,test,threshold,rc,wall,rss,user,sy = m.groups()
        rows.append(dict(tag=tag,test=test,threshold=threshold,rc=int(rc),wall=float(wall),
                         rss_kb=int(rss),user=float(user),sys=float(sy)))

if not rows:
    raise SystemExit("V118: no result rows")

# Candidate policy frontier over successful Mathlib + con-leche pairs only.
by=defaultdict(dict)
for r in rows:
    if r["tag"]=="SELECTOR":
        by[r["threshold"]][r["test"]]=r

pts=[]
for th,d in by.items():
    if "mathlib" in d and "con-leche" in d and d["mathlib"]["rc"]==0 and d["con-leche"]["rc"]==0:
        pts.append((th,d["mathlib"]["wall"],d["con-leche"]["wall"]))

frontier=[]
for p in pts:
    dominated=False
    for q in pts:
        if q==p: continue
        if q[1] <= p[1] and q[2] <= p[2] and (q[1] < p[1] or q[2] < p[2]):
            dominated=True
            break
    if not dominated:
        frontier.append(p)

print("V118_ANALYSIS_BEGIN")
for th,m,c in sorted(pts,key=lambda x:(x[1],x[2],int(x[0]))):
    print(f"V118_POINT threshold={th} mathlib_wall={m:.2f} con_leche_wall={c:.2f}")
for th,m,c in sorted(frontier,key=lambda x:(x[1],x[2],int(x[0]))):
    print(f"V118_PARETO threshold={th} mathlib_wall={m:.2f} con_leche_wall={c:.2f}")
print("V118_ANALYSIS_END")
print("V118_ANALYSIS_COMPLETE=PASS")
