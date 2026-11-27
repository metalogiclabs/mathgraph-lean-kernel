"""Keep wall-time usefulness separate from instruction-based ranking costs."""
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
subprocess.run(['python3',str(root/'experiments/flash-env-handoff-20261127/full_gate.py'),'--mode',a.mode,'--out',str(a.out)],check=True)
result=json.loads((a.out/'handoff-gate.json').read_text())
if a.mode=='native':
 rows=json.loads((a.out/'native/rows.json').read_text())
 medians={arm:statistics.median(r['wall_s'] for r in rows if r['arm']==arm) for arm in ['baseline','strict']}
 ratio=medians['strict']/medians['baseline']
 paired=[next(r['wall_s'] for r in rows if r['arm']=='strict' and r['round']==i)/next(r['wall_s'] for r in rows if r['arm']=='baseline' and r['round']==i) for i in [0,1]]
 result['checks']['wall_regression_at_most_three_percent']=ratio<=1.03
 result['details'].update(wall_medians_s=medians,wall_ratio=ratio,paired_wall_ratios=paired)
 result['practical_wall_improvement_observed']=ratio<=.99 and all(x<1 for x in paired)
result['passed']=all(result['checks'].values())
result['boundary']='Matched two-worker complete Mathlib experiment. Instruction savings alone do not establish useful elapsed-time improvement. Other nine large cases and Arena-native scoring remain separate.'
(a.out/'stack-gate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
if not result['passed']:raise SystemExit(1)
