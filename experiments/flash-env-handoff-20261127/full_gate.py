"""Apply the predeclared full-input gates, preserving each measurement boundary."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--mode',choices=['native','instructions'],required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
subprocess.run(['python3',str(root/'experiments/flash-session-budget-20261126/full_gate.py'),'--mode',a.mode,'--out',str(a.out)],check=True)
original=json.loads((a.out/'gate.json').read_text())
if a.mode=='native':
    rows=json.loads((a.out/'native/rows.json').read_text())
    medians={arm:statistics.median(r['cpu_s'] for r in rows if r['arm']==arm) for arm in ['baseline','strict']}
    ratio=medians['strict']/medians['baseline']
    original['checks']['cpu_regression_at_most_three_percent']=ratio<=1.03
    original['details']['cpu_medians_s']=medians
    original['details']['cpu_ratio']=ratio
original['passed']=all(original['checks'].values())
original['boundary']='Exact complete-Mathlib experiment only. Nine other large inputs and official native retired-instruction Arena scoring remain separate.'
(a.out/'handoff-gate.json').write_text(json.dumps(original,indent=2)+'\n')
print(json.dumps(original),flush=True)
if not original['passed']:raise SystemExit(1)
