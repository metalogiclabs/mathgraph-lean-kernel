"""Combine source-bound public verifier matrices without changing primary costs.

Artifact/run provenance must be attested by the caller. This function refuses
mixed sources, mixed harnesses, duplicate or missing required-version evidence.
The existing frontier admission gate remains the final authority.
"""
import copy

def merge_versions(primary,others,required):
 if not required:raise ValueError('required versions missing')
 identity=['name','candidate_label','proof_sha256','public_harness_sha']
 if any(not primary.get(k) for k in identity):raise ValueError('unbound primary identity')
 compat={};records={};untested=[]
 for result in [primary,*others]:
  if any(result.get(k)!=primary[k] for k in identity):raise ValueError('mixed source or verifier identity')
  if result.get('statement_ok') is False or result.get('forbidden') or result.get('extra_toplevel_decls'):raise ValueError('explicit declaration rejection')
  pv=result.get('per_version') or []
  c=result.get('compat') or {}
  if len(pv)!=len(c) or {r.get('version') for r in pv}!=set(c):raise ValueError('incoherent version matrix')
  for record in pv:
   v=record['version']
   if v in records:raise ValueError('duplicate version evidence')
   if record.get('ok') is not c[v]:raise ValueError('inconsistent version verdict')
   records[v]=copy.deepcopy(record);compat[v]=c[v]
  untested.extend(result.get('untested') or [])
 if len(required)!=len(set(required)) or set(records)!=set(required):raise ValueError('required coverage incomplete or unexpected')
 out=copy.deepcopy(primary)
 out.update(compat=compat,per_version=[records[v] for v in required],untested=untested,
  all_versions=True,measurement_scope='all_required_composed_native_runs')
 positive=sum(compat[v] is True and records[v].get('tested') is True for v in required)
 out['survival_pct']=round(100*positive/len(required),2)
 out['eligible']=primary.get('eligible') is True and positive==len(required) and not untested
 return out
