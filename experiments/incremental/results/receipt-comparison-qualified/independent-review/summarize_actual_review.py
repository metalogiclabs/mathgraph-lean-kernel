#!/usr/bin/env python3
"""Summarize already independently reviewed raw observations; no runtime imports."""
import hashlib,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
load=lambda p:json.loads(Path(p).read_bytes())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=load(P/'actual-ci/review.json')
assert review['passed'] and review['helper_sha256']=='915467911481d05949e824eca0e707c5fdbef87967134f0605040008f805574d'
r=load(P/'actual-ci/artifact/receipt-comparison/summary.json');med=statistics.median
phase_names=('producer_seconds','baseline_validation_seconds','identity_update_seconds','materialization_and_hash_seconds','checking_seconds','persistence_seconds')
out=dict(source=r['source_sha'],run_id=39581949051,job_id=119161428100,artifact_id=12342450124,archive_sha256='7aa231dff8ddda4d1f6cbd073d62ea408ac5e8f491f421f1ceeebfa5a01f4847',archive_bytes=58533476,review_sha256=sha(P/'actual-ci/review.json'),helper_sha256=review['helper_sha256'],checks=review['check_count'],falsifiers=len(review['falsifiers']),legacy=review['legacy'],protected=review['protected'],host=r['host'],profiles={},cold={})
for profile in ('original','expanded'):
 out['profiles'][profile]={};out['cold'][profile]={}
 for variant in ('early-definition','unrelated-definition'):
  case=r['profiles'][profile][variant];v={key:case[key] for key in ('warm_economics','warm_cpu_economics','persistence_economics','setup_plus_one_apply_component_sum_economics','direct_full_rust_economics')};v['arms']={}
  for mode in ('canonical_json','shared_json'):
   aa=[x['arms'][mode] for x in case['pairs']];timings=[a['phases']['timings'] for a in aa]
   residual=[a['wall_seconds']-sum(a['phases']['timings'][key] for key in phase_names) for a in aa]
   memory={}
   for process in ('adapter','producer','index','retained_kernel'):
    memory[process]={}
    for field in ('VmRSS','VmHWM'):
     values=[a['phases']['memory']['persistence']['processes'].get(process) for a in aa]
     values=[value[field] for value in values if isinstance(value,dict) and field in value]
     memory[process][field]=dict(observed_samples=len(values),median_procfs_kB=med(values) if values else None)
   v['arms'][mode]=dict(warm_wall_seconds=med(a['wall_seconds'] for a in aa),warm_cpu_seconds=med(t['end_to_end_cpu_seconds'] for t in timings),persistence_seconds=med(a['persistence_seconds'] for a in aa),direct_rust_wall_seconds=med(a['direct_rust']['wall_seconds'] for a in aa),direct_rust_cpu_seconds=med(a['direct_rust']['completed_child_cpu_seconds'] for a in aa),fresh_baseline_setup_seconds=med(a['setup_seconds'] for a in aa),phase_medians_seconds={key:med(t[key] for t in timings) for key in phase_names},outer_apply_samples_seconds=[a['wall_seconds'] for a in aa],unassigned_apply_samples_seconds=residual,unassigned_apply_median_seconds=med(residual),post_persistence_memory=memory)
  out['profiles'][profile][variant]=v
 for mode,cold in r['profiles'][profile]['cold_restart'].items():
  a=cold['arm'];out['cold'][profile][mode]=dict(setup_seconds=a['setup_seconds'],setup_cpu_seconds=a['setup_report']['cpu_seconds'],apply_seconds=a['wall_seconds'],apply_cpu_seconds=a['phases']['timings']['end_to_end_cpu_seconds'],setup_plus_apply_components_seconds=a['setup_plus_apply_component_sum_seconds'],baseline_scope=a['baseline_result']['scope'],baseline_counts=a['baseline_result']['counts'],producer_memory_observation=a['phases']['memory']['producer'])
w=review['representative_witnesses'];out['witness_inventory']=dict(representatives=len(w),replayed_decisions=sum(v['obligations'] for v in w.values()),selected_checked=sum(v['checked'] for v in w.values()),historical_hmac_authenticated_by_this_review=False)
out['limits']=review['limitations']+['Bootstrap intervals are pointwise with five pairs, not familywise simultaneous confidence.','Medians of correlated phase components do not add to the median total; unassigned overhead spikes are observed but not profiled to a specific cause.']
(P/'actual-ci/findings.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('checks','falsifiers','witness_inventory')}))
