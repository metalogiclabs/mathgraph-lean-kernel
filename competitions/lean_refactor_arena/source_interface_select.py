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
def transfer(rows, source_name, target_name):
    """Fit an operator on source outcomes only, then score fixed target use.

    Targets are previously inspected warmups, not blind heldouts. A target's
    independent winner must never change the source-selected operator.
    """
    source=[r for r in rows if r['name']==source_name]
    fit=select(source)['results']
    if len(fit)!=1: raise ValueError('missing source')
    winner=next(r for r in source if r['candidate_label']==fit[0]['selected_label'])
    result={'source_name':source_name,'target_name':target_name,
      'frozen_operator':winner['operator'],'source_selected_label':winner['candidate_label'],
      'source_objective_gain':fit[0]['objective_gain'],
      'target_cost_used_for_selection':False,'blind_heldout':False,
      'ablation':'v16_control deletes the acquired source representation operator'}
    if winner['operator']=='control': return dict(result,status='NO_SOURCE_GAIN')
    target=[r for r in rows if r['name']==target_name]
    controls=[r for r in target if r['candidate_label']=='v16_control']
    if len(controls)!=1 or not lawful(controls[0]): raise ValueError('target control failed')
    candidates=[r for r in target if r['operator']==winner['operator']]
    if not candidates:return dict(result,status='NO_APPLICABLE_TRANSFER')
    # Stable source order is fixed before observing target cost. No target max.
    chosen=candidates[0];base=controls[0]
    qualified=lawful(chosen)
    gain=float(chosen['objective_sum_pct'])-float(base['objective_sum_pct']) if qualified else None
    return dict(result,status='MEASURED_OPERATOR_TRANSFER' if qualified and gain>0 else 'TRANSFER_FAILED_OR_NONDOMINANT',
      target_label=chosen['candidate_label'],target_qualified=qualified,target_objective_gain=gain)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('results');ap.add_argument('--out',required=True);a=ap.parse_args()
    result=select([json.loads(x) for x in Path(a.results).read_text().splitlines() if x.strip()])
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
