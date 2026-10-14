#!/usr/bin/env python3
"""Select only measured, fully qualified improvements; never edit the portfolio."""
import argparse,json
from pathlib import Path

def lawful(row):
    pv=row.get('per_version') or []
    return (row.get('compiled') is True and row.get('statement_ok') is True
        and row.get('eligible') is True and row.get('compat')=={'v4.32.0':True}
        and len(pv)==1 and pv[0].get('version')=='v4.32.0'
        and pv[0].get('tested') is True and pv[0].get('ok') is True
        and not row.get('untested') and not row.get('forbidden')
        and not row.get('extra_toplevel_decls'))

def select(rows):
    results=[]
    for name in dict.fromkeys(r['name'] for r in rows):
        group=[r for r in rows if r['name']==name]
        controls=[r for r in group if r['candidate_label']=='v16_control']
        if len(controls)!=1 or not lawful(controls[0]): raise ValueError('control failed qualification: '+name)
        base=controls[0]
        candidates=[r for r in group if lawful(r) and float(r['objective_sum_pct'])>float(base['objective_sum_pct'])]
        winner=max(candidates,key=lambda r:(float(r['objective_sum_pct']),-int(r['length']),r['candidate_label']),default=base)
        results.append({'name':name,'status':'MEASURED_GAIN_NOT_PROMOTED' if winner is not base else 'NO_MEASURED_GAIN',
          'selected_label':winner['candidate_label'],'control_length':base['length'],'control_heartbeats':base['heartbeats'],
          'selected_length':winner['length'],'selected_heartbeats':winner['heartbeats'],
          'objective_gain':float(winner['objective_sum_pct'])-float(base['objective_sum_pct']),
          'attempted_candidates':len(group)-1,'qualified_candidates':sum(lawful(r) for r in group)-1})
    return {'schema':'mathgraph.lra.source-interface-selection.v1','results':results,
      'rule_frozen_before_measurement':True,'blind_heldout':False,'portfolio_changed':False,
      'boundary':'Bounded source-derived representations of existing witnesses; no new mathematical lemma or grammar invention.'}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('results');ap.add_argument('--out',required=True);a=ap.parse_args()
    result=select([json.loads(x) for x in Path(a.results).read_text().splitlines() if x.strip()])
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
