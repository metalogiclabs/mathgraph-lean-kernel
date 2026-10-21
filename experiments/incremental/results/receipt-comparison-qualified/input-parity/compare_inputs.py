#!/usr/bin/env python3
"""Compare extracted CI-reported snapshot SHA/size to fixed fresh74-process replay.

No engine, producer, native process or issuer key is loaded. Compact report hash
identity is not remote-machine attestation or a new economic measurement.
"""
import argparse,hashlib,json
from pathlib import Path
LOCAL_SHA='97ae21b2dfaa46944ca8415044b7758b64d2605c7a0fb73bea4cbc380a677f6f'
NEGATIVES=('signed-invalid-proof','signed-invalid-axiom','unused-invalid-node-zero-selection-parser','unused-invalid-node-dag-only-zero-selection-parser')
POSITIVES=('early-definition','unrelated-definition')
MODES=('canonical_json','shared_json')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def hexid(v):return type(v)is str and len(v)==64 and all(c in'0123456789abcdef'for c in v)
def repetitions(rows):
 values=[r.get('repetition')if type(r)is dict else None for r in rows]
 return len(values)==5 and all(type(v)is int for v in values)and sorted(values)==list(range(5))
def compare(local,protected,comparison):
 missing=[];mismatched=[];metadata_errors=[];observations=[];extra_ci=[];claims=[];outside=[];by_role={}
 def error(where,reason):metadata_errors.append(dict(where=where,reason=reason))
 for field,native in [('full_case_inputs',False),('retained_case_inputs',True)]:
  for row in local[field]:
   name=row['name'];profile=row['profile'];digest=row['complete_input_sha256']if native else row['sha256'];size=row['complete_input_bytes']if native else row['bytes'];key=(profile,name)
   claim=dict(group=field,profile=profile,role=name,sha256=digest,bytes=size)
   if name=='overwrite-admitted-expression':outside.append(dict(claim,classification='LOCAL_ONLY_CONSERVATIVE_OVERWRITE_POLICY',scope='No corresponding CI kernel-negative role expected; fresh zero-selected parser accepted while retained policy refused.'));continue
   if key in by_role and by_role[key]!=(digest,size):error(field,'inconsistent local repeated role '+repr(key))
   by_role[key]=(digest,size);claims.append(claim)
 def observe(profile,role,where,snapshot,reported_outcome):
  expected=by_role.get((profile,role));record=dict(profile=profile,role=role,where=where,reported_outcome=reported_outcome)
  if expected is None:extra_ci.append(dict(record,reason='Outside local full/native replay coverage'));return
  record.update(expected_sha256=expected[0],expected_bytes=expected[1])
  if type(snapshot)is not dict or 'sha256'not in snapshot or 'bytes'not in snapshot:
   missing.append(dict(record,missing_fields=['sha256','bytes']if type(snapshot)is not dict else[k for k in['sha256','bytes']if k not in snapshot]));return
  record.update(actual_sha256=snapshot['sha256'],actual_bytes=snapshot['bytes'])
  if not hexid(snapshot['sha256'])or type(snapshot['bytes'])is not int or snapshot['bytes']<0:
   mismatched.append(dict(record,reason='Malformed reported snapshot hash/size'));return
  if(snapshot['sha256'],snapshot['bytes'])!=expected:mismatched.append(dict(record,reason='Exact SHA256 or byte size differs'));return
  observations.append(dict(record,exact_sha_and_size_match=True))
 for profile in['original','expanded']:
  q=protected.get(profile)
  if type(q)is not dict:
   missing.append(dict(where='receipt-protected/'+profile,reason='Missing or unreadable protected summary'));continue
  if q.get('source_git_commit')!=local['source']or q.get('source_git_status')!='':error('protected/'+profile,'wrong or dirty source')
  if not(q.get('run_completed')and q.get('correctness_passed')and q.get('qualification_status')=='PASS'):error('protected/'+profile,'protected report not complete PASS')
  samples=q.get('samples',[])
  for role in POSITIVES:
   chosen=[s for s in samples if type(s)is dict and s.get('variant')==role]
   expected_count=6 if role=='early-definition'else 5
   if len(chosen)!=expected_count:error('protected/'+profile+'/'+role,'expected '+str(expected_count)+' snapshots, got '+str(len(chosen)))
   if not repetitions([s for s in chosen if not s.get('cold_replay')])or sum(s.get('cold_replay')is True for s in chosen)!=(1 if role=='early-definition'else 0):error('protected/'+profile+'/'+role,'warm/cold repetitions missing or duplicated')
   for n,s in enumerate(chosen):
    where=f'protected/{profile}/samples/{role}/{n}'
    if not s.get('evidence_id')or s.get('direct_rust',{}).get('returncode')!=0 or s.get('direct_rust',{}).get('timed_out'):error(where,'reported positive outcome invalid')
    observe(profile,role,where,s.get('snapshot'),'ACCEPTED_REPORTED')
  for s in samples:
   if type(s)is dict and s.get('variant')not in POSITIVES:extra_ci.append(dict(profile=profile,role=s.get('variant'),reason='Protected positive role outside local full/native replay coverage'))
  for role in NEGATIVES:
   c=q.get('controls',{}).get(role)
   if type(c)is not dict:
    missing.append(dict(profile=profile,role=role,where='protected/controls',reason='Missing kernel-negative control'));continue
   result=c.get('result',{});where='protected/'+profile+'/controls/'+role
   if result.get('status')!='REJECTED'or result.get('checker_result',{}).get('code')!=1 or result.get('evidence_id')is not None or result.get('receipt_id')is not None:error(where,'negative outcome or absence of acceptance invalid')
   independent=c.get('independent_kernel_rejections',{})
   if len(independent)<3 or any(x.get('returncode')!=1 or x.get('timed_out')for x in independent.values()):error(where,'full independent rejection reports missing or invalid')
   if role.startswith('unused-invalid-node'):
    zero=c.get('independent_zero_selected_parser',{})
    if result.get('counts',{}).get('scheduled')!=0 or zero.get('returncode')!=1 or zero.get('timed_out'):error(where,'zero-selected parser refusal not recorded')
   gate=next((g for g in q.get('gates',[])if g.get('name')=='no_new_persisted_acceptance:'+role),None)
   if gate is None or gate.get('passed')is not True:error(where,'missing successful no-persisted-acceptance gate')
   observe(profile,role,where,c.get('snapshot'),'REJECTED_REPORTED')
 if type(comparison)is not dict:missing.append(dict(where='receipt-comparison/summary.json',reason='Missing or unreadable comparison summary'))
 else:
  if comparison.get('source_sha')!=local['source']:error('comparison','wrong source')
  if comparison.get('schema')!='mathgraph.retained-receipt-index-comparison.v1'or not all(comparison.get(k)is True for k in['completed','correctness_passed','qualified']):error('comparison','wrong schema or incomplete report')
  for profile in['original','expanded']:
   p=comparison.get('profiles',{}).get(profile,{})
   for role in POSITIVES:
    row=p.get(role,{})
    if row.get('complete')is not True or len(row.get('pairs',[]))!=5:error('comparison/'+profile+'/'+role,'incomplete five paired samples')
    if not repetitions(row.get('pairs',[])):error('comparison/'+profile+'/'+role,'paired repetitions missing or duplicated')
    for n,pair in enumerate(row.get('pairs',[])):
     for mode in MODES:
      arm=pair.get('arms',{}).get(mode);where=f'comparison/{profile}/{role}/{n}/{mode}'
      if type(arm)is not dict:missing.append(dict(where=where,reason='Missing comparison arm'));continue
      if arm.get('signed_comparison_policy')!=mode or arm.get('kernel_report',{}).get('code')!=0 or arm.get('direct_rust',{}).get('returncode')!=0 or arm.get('direct_rust',{}).get('timed_out'):error(where,'reported accepted arm or signed policy invalid')
      snap=arm.get('snapshot');observe(profile,role,where,snap,'ACCEPTED_REPORTED')
      if type(snap)is dict and arm.get('export_sha256')!=snap.get('sha256'):error(where,'arm export hash differs from snapshot hash')
   for mode in MODES:
    cold=p.get('cold_restart',{}).get(mode);where=f'comparison/{profile}/cold_restart/{mode}'
    if type(cold)is not dict or type(cold.get('arm'))is not dict:missing.append(dict(where=where,reason='Missing cold replay arm'));continue
    if cold.get('passed')is not True:error(where,'cold replay did not pass')
    arm=cold['arm']
    if arm.get('signed_comparison_policy')!=mode or arm.get('kernel_report',{}).get('code')!=0 or arm.get('direct_rust',{}).get('returncode')!=0 or arm.get('direct_rust',{}).get('timed_out'):error(where,'reported cold accepted arm invalid')
    observe(profile,'early-definition',where,cold['arm'].get('snapshot'),'COLD_ACCEPTED_REPORTED')
 coverage=[]
 for claim in claims:
  hits=[o for o in observations if(o['profile'],o['role'])==(claim['profile'],claim['role'])]
  bad=[o for o in missing+mismatched if(o.get('profile'),o.get('role'))==(claim['profile'],claim['role'])]
  coverage.append(dict(claim,matching_snapshot_count=len(hits),claim_supported=bool(hits)and not bad))
  if not hits and not bad:missing.append(dict(profile=claim['profile'],role=claim['role'],where='CI snapshot coverage',reason='Local replay role has no exact CI observation'))
 passed=not(missing or mismatched or metadata_errors)
 return dict(status='PASS_EXACT_REPORTED_CI_INPUT_PARITY'if passed else'FAIL_MISSING_MISMATCH_OR_METADATA',source=local['source'],matches=observations,missing=missing,mismatched=mismatched,metadata_errors=metadata_errors,local_claim_coverage=coverage,extra_local_overwrite_roles=outside,extra_ci_roles_outside_replay=extra_ci,counts=dict(matched_snapshots=len(observations),covered_role_keys=len({(x['profile'],x['role'])for x in observations}),local_claims=len(claims),extra_local_overwrite_roles=len(outside),missing=len(missing),mismatched=len(mismatched),metadata_errors=len(metadata_errors)),scope=['Compares explicit CI snapshot SHA256 AND exact integer byte sizes to fixed actual74-process replay inputs.','Compact reports supply CI input identity under SHA256 collision resistance; no remote process/machine attestation is inferred.','Reported outcomes and no-persistence gates are checked separately from input identity; HMAC keys and economic claims are not inspected.','Extra local overwrite-policy roles are intentionally outside CI-role coverage, not silently counted as matches.','Baseline/theorem-leaf protected positives outside local full-kernel replay are listed as extra CI scope, not certified by this helper.'])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ci-root',required=True,type=Path);p.add_argument('--local-summary',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 raw=a.local_summary.read_bytes()
 if sha(raw)!=LOCAL_SHA:raise ValueError('Local74-process replay summary changed from frozen hash')
 local=json.loads(raw);protected={};files={}
 def load(path):
  if not path.exists():return None
  data=path.read_bytes();files[str(path.relative_to(a.ci_root))]=dict(sha256=sha(data),bytes=len(data));return json.loads(data)
 for profile in['original','expanded']:protected[profile]=load(a.ci_root/'receipt-protected'/profile/'protected-matrix/retained_selected/summary.json')
 comparison=load(a.ci_root/'receipt-comparison/summary.json');report=compare(local,protected,comparison);report.update(local_summary_sha256=sha(raw),ci_report_files=files,helper_sha256=sha(Path(__file__).read_bytes()))
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(dict(status=report['status'],counts=report['counts'],output_sha256=sha(a.out.read_bytes()))))
 if report['status']!='PASS_EXACT_REPORTED_CI_INPUT_PARITY':raise SystemExit(1)
if __name__=='__main__':main()
