#!/usr/bin/env python3
"""Compare compact CI input hashes with actual independent full-kernel replay.

This audits reported SHA256 input identity; the compact archive omits live CI
memfds and issuer secrets. No economic or remote-machine attestation is inferred.
"""
import argparse,gzip,hashlib,json
from pathlib import Path
import zipfile
HERE=Path(__file__).resolve().parent

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--package',type=Path,default=HERE)
 a=p.parse_args();package=a.package.resolve();recipes=load(package/'recipes.json')
 observed_raw=(package/'as-run/summary.json').read_bytes();observed=json.loads(observed_raw)
 assert sha(observed_raw)==recipes['observations']['as_run_summary_sha256']
 assert observed['status']=='PASS_INDEPENDENT_CURRENT_AND_QUALIFIED449_REAL_KERNEL_REPLAY'
 case_map={(c['profile'],c['name']):c for c in recipes['cases']}
 file_map={r['original_path']:r for r in load(package/'as-run-file-map.json')}
 def observed_file(original):
  # Absolute original paths remain metadata; lookup by the preserved replay-root suffix.
  root=Path(observed['cases'][0]['reconstruction']['path']).parent
  entry=file_map[str(Path(original).relative_to(root))]
  raw=(package/entry['path']).read_bytes();assert sha(raw)==entry['sha256']
  raw=gzip.decompress(raw) if entry['encoding']=='gzip' else raw
  assert sha(raw)==entry['original_sha256'] and len(raw)==entry['original_bytes']
  return raw
 actual_commands=0
 for case in observed['cases']:
  recipe=case_map[case['profile'],case['name']]
  assert recipe['expected_sha256']==case['reconstruction']['sha256']
  for command in case['kernels']:
   assert command['returncode']==command['expected_returncode']==recipe['expected_returncode']
   for stream in ['stdout','stderr']:
    assert sha(observed_file(command[stream+'_path']))==command[stream+'_sha256']
   actual_commands+=1
 assert actual_commands==48
 with zipfile.ZipFile(a.zip) as z:
  source=z.read('source-ref.txt').decode().strip();assert source==recipes['source']
  observations=json.loads(z.read('ci-observations.json'))
  assert observations['source_sha']==source and not observations['failures']
  manifest={line.split(None,1)[1].lstrip('*'):line.split(None,1)[0] for line in z.read('source-SHA256SUMS').decode().splitlines()}
  source_parity={}
  for records in observed['measured_source_matches_current_commit'].values():
   for name,digest in records.items():assert manifest[name]==digest;source_parity[name]=digest
  reports={};members={}
  for profile,member in [('original','delta-qualification/summary.json'),('expanded','delta-expanded-qualification/summary.json')]:
   raw=z.read(member);r=json.loads(raw);reports[profile]=r
   assert r['source_git_commit']==source and r['source_git_status']==''
   assert r['run_completed'] and r['correctness_passed'] and r['qualification_status']=='PASS'
   assert len(r['gates'])>=(243 if profile=='original' else 226) and all(g['passed']is True for g in r['gates'])
   label='producer-delta'+('-expanded' if profile=='expanded' else '')
   assert observations['reports'][label]['summary_sha256']==sha(raw)
   members[profile]=dict(member=member,sha256=sha(raw),gates=len(r['gates']))
  retained=json.loads(z.read('retained-qualification/summary.json'))
 positives=[];controls=[]
 for profile,r in reports.items():
  expected=case_map[profile,'early-definition']
  samples=[s for s in r['samples'] if s['variant']=='early-definition']
  assert len(samples)==6 and sum(s['cold_replay'] for s in samples)==1
  for sample in samples:
   snap=sample['snapshot'];assert snap['sha256']==expected['expected_sha256'] and snap['bytes']==expected['expected_bytes']
   assert snap['seals']&15==15 and sample['evidence_id']
   assert sample['direct_rust']['returncode']==0 and not sample['direct_rust']['timed_out']
   positives.append(dict(profile=profile,repetition=sample['repetition'],cold_replay=sample['cold_replay'],sha256=snap['sha256'],bytes=snap['bytes'],exact_independent_input_parity=True))
  assert r['references']['early-definition']['typed_index_sha256']==recipes['source_exports'][profile]['typed_index_sha256']
  for (case_profile,name),expected in case_map.items():
   if case_profile!=profile or name=='early-definition':continue
   c=r['controls'][name];snap=c['snapshot'];result=c['result']
   assert snap['sha256']==expected['expected_sha256'] and snap['bytes']==expected['expected_bytes']
   assert result['status']=='REJECTED' and result['checker_result']['code']==1
   assert result.get('evidence_id')is None and result.get('receipt_id')is None
   assert next(g for g in r['gates'] if g['name']=='no_new_persisted_acceptance:'+name)['passed']is True
   for command in c['independent_kernel_rejections'].values():assert command['returncode']==1 and not command['timed_out']
   if expected['zero_selected_parser']:
    assert result['counts']['scheduled']==0
    assert c['independent_zero_selected_parser']['returncode']==1 and not c['independent_zero_selected_parser']['timed_out']
   controls.append(dict(profile=profile,name=name,sha256=snap['sha256'],bytes=snap['bytes'],exact_independent_input_parity=True,ci_selected_and_full_kernels_reject=True,ci_no_accepted_evidence=True,zero_selected_parser_rejects=expected['zero_selected_parser']))
 matrix=[]
 assert retained['source_sha']==recipes['source'] and retained['run_completed'] and retained['correctness_passed']
 for sample in retained['samples']:
  if sample['variant']!='early-definition':continue
  expected=case_map[sample['profile'],'early-definition']
  for arm,record in sample['arms'].items():
   snap=record['sealed_snapshot'];assert snap['sha256']==expected['expected_sha256'] and snap['bytes']==expected['expected_bytes']
   matrix.append(dict(profile=sample['profile'],repetition=sample['repetition'],arm=arm,sha256=snap['sha256']))
 assert len(matrix)==30
 tool_map={'current-rust':'full_checker','current-zero-selected':'checker','normal-cpp':'leanchecker','paranoid-cpp':'leanchecker-paranoid','current-index':'indexer'}
 tool_parity={name:dict(local_sha256=info['sha256'],ci_sha256=reports['original']['tools'][tool_map[name]]['sha256'],equal=info['sha256']==reports['original']['tools'][tool_map[name]]['sha256']) for name,info in observed['actual_tools'].items() if name in tool_map}
 for name,ci_name in [('qualified449-rust','qualified449_sokonanoda'),('qualified449-zero-selected','qualified449_check-selected'),('qualified449-index','qualified449_export-index')]:
  local=observed['actual_tools'][name]['sha256'];ci=retained['tools'][ci_name]['sha256'];tool_parity[name]=dict(local_sha256=local,ci_sha256=ci,equal=local==ci)
 verdict=dict(status='PASS_EXACT_CI_INPUT_PARITY_WITH_40_FULL_AND_8_ZERO_SELECTED_REPLAY',source=source,ci_zip_sha256=sha(a.zip.read_bytes()),ci_members=members,as_run_summary_sha256=sha(observed_raw),local_raw_kernel_outputs_revalidated=48,positives=positives,controls=controls,retained_matrix_early_arms=matrix,critical_source_parity=source_parity,tool_binary_parity=tool_parity,helper_sha256=sha(Path(__file__).read_bytes()),scope=['Input parity uses compact-CI reported SHA256s and collision resistance; CI live input bytes/caches and private issuer key are omitted.','Independent local current and449 Rust plus normal/paranoid C++ actually executed these exact reconstructed inputs.','Local recorded dirty1e20 source and incomplete smoke are preserved; measured-source equality to clean ef434 is separate evidence.','Different native executable build hashes do not become exact binary parity. This is not CI economic remeasurement or machine attestation.'])
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(verdict,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(status=verdict['status'],positive_samples=len(positives),invalid_controls=len(controls),matrix_arms=len(matrix),output_sha256=sha(a.out.read_bytes()))))
if __name__=='__main__':main()
