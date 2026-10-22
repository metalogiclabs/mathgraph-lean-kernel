from decimal import Decimal, getcontext
import json
from pathlib import Path
import zipfile
getcontext().prec=100
ROOT=Path(__file__).parent
ZIP=Path('/workspace/kernel-audit/revision-lifecycle/ci-d1b2244/revision-chain-summaries-d1b2244.zip')
def load(s): return json.loads(s,parse_float=Decimal)
def plain(v):
 if isinstance(v,Decimal):return str(v)
 if isinstance(v,dict):return {k:plain(x) for k,x in v.items()}
 if isinstance(v,list):return [plain(x) for x in v]
 return v
def stats(v):
 s=sorted(Decimal(x) for x in v); n=len(s); return {'count':n,'min':s[0],'median':s[n//2] if n%2 else(s[n//2-1]+s[n//2])/2,'max':s[-1]}
def total(v):return sum((Decimal(x) for x in v),Decimal(0))
with zipfile.ZipFile(ZIP) as z:
 names=[n for n in z.namelist() if n.endswith('revision-chain/summary.json')]; assert len(names)==1
 report=load(z.read(names[0]))
a=load((ROOT/'analysis.json').read_text())
out={'scope':'Actual ZIP contextual arithmetic only; source economics copied without inventing a new qualification or confidence interval. Warm per-edit values are separate arm observations.','source_sha':report['source_sha'],'flags':{k:report[k] for k in ('repetitions','cycles','completed','correctness_passed','qualified','qualification_status','source_tracked_clean','source_and_binary_stable')},'profiles':{}}
for name,p in report['profiles'].items():
 ap=a['profiles'][name]; seq=ap['sequences']; rows=[r for q in seq for r in q['continuous']['rows']]
 samples=[s for q in p['pairs'] for s in q['steps']]
 warm={}
 for edit in sorted({s['name'] for s in samples}):
  steps=[s for s in samples if s['name']==edit]; crows=[r for r in rows if r['name']==edit]
  warm[edit]={'count':len(steps),'continuous_apply_wall_seconds':stats([Decimal(r['wall']['apply_seconds']) for r in crows]),'continuous_apply_cpu_seconds':stats([Decimal(r['cpu']['apply_cpu_seconds']) for r in crows]),'interleaved_external_apply_wall_seconds':stats([s['apply_wall_seconds'] for s in steps]),'same_input_fresh_rust_command_wall_seconds':stats([s['direct_rust']['wall_seconds'] for s in steps]),'actual_checked':sorted({s['partition_audit']['actual_kernel_checked'] for s in steps}),'actual_total':sorted({s['partition_audit']['actual_kernel_total'] for s in steps})}
 phase={field:{'sequence_sums':ap['continuous_per_sequence_sum_statistics'][field],'pooled_update_share':ap['continuous_pooled_update_phase_shares'][field]} for field in ap['continuous_pooled_update_phase_shares']}
 gaps={field:{'sequence_sums':ap['continuous_per_sequence_sum_statistics'][field],'pooled_update_share':ap['continuous_pooled_update_gap_shares'][field]} for field in ap['continuous_pooled_update_gap_shares']}
 economics={field:p[field] for field in ('continuous_economics','continuous_cpu_economics','economics','cpu_economics')}
 cold=[q['cold_replay'] for q in seq if q['cold_replay'] is not None]
 native=[q['interleaved']['native_identity_observations'] for q in seq]
 rev=p['revision_economics']
 out['profiles'][name]={'dimensions':ap['source_dimensions'],'reported_economics':economics,'warm_per_edit':warm,'continuous_start_wall_seconds':stats([q['continuous']['residuals']['start_report_wall_seconds'] for q in seq]),'continuous_start_cpu_seconds':stats([q['continuous']['residuals']['start_report_cpu_seconds'] for q in seq]),'continuous_outer_wall_seconds':stats([q['continuous']['outer_wall_seconds'] for q in seq]),'continuous_outer_cpu_seconds':stats([q['continuous']['outer_cpu_seconds'] for q in seq]),'continuous_update_api_sum_wall_seconds':ap['continuous_per_sequence_sum_statistics']['apply_seconds'],'continuous_update_api_sum_cpu_seconds':stats([q['continuous']['cpu_sums']['apply_cpu_seconds'] for q in seq]),'continuous_outer_constructor_close_recording_residual_wall_seconds':stats([q['continuous']['residuals']['constructor_close_compact_recording_wall_residual'] for q in seq]),'phase_sum_statistics':phase,'largest_named_phase_per_sequence':ap['largest_named_phase_per_sequence'],'unclassified_gaps':gaps,'negative_residuals':[q['continuous']['sums']['negative_residual_revisions'] for q in seq],'chain_promotion_nested_sequence_sums':ap['continuous_per_sequence_sum_statistics']['chain_promotion_nested_seconds'],'receipt_persistence_before_promotion_sequence_sums':ap['continuous_per_sequence_sum_statistics']['receipt_persistence_before_promotion_seconds'],'continuous_work_per_sequence':[q['continuous']['work'] for q in seq],'native_finish_observations':native,'cold':cold,'published_per_revision_economic_status_counts':{status:sum(e['economics']['status']==status for e in rev) for status in {e['economics']['status'] for e in rev}},'published_per_revision_median_ratio_range':stats([e['economics']['median_ratio'] for e in rev])}
(ROOT/'contextual-brief.json').write_text(json.dumps(plain(out),indent=2,sort_keys=True)+'\n')
print(json.dumps(plain(out),indent=2,sort_keys=True))
