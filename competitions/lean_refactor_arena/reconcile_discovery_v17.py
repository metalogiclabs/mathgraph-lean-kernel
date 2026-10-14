#!/usr/bin/env python3
"""Reclose completed source-acquisition native evidence using existing admission.

V16 bytes remain immutable in git/official receipt. Only positively qualified
native improvements enter V17. This does not establish hosted scoring or budget.
"""
import argparse,copy,hashlib,json,pathlib,subprocess
from frontier_reclose import reclose_packet
ROOT=pathlib.Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE='6a942a2af66ae585bb91da60b0fa291309f81e13'
HEAD='5860c36449b76e182add6d78311b76eeda5e8d74'
PIN='7f3a401470d04f70013d293db4253b088ec8a0ae'
EV=ROOT/'evidence/native_closure_discovery_v3'
PORT=ROOT/'portfolio/warmup_portfolio_v1.jsonl'
PACKET=ROOT/'submissions/mathgraph_verified_15_warmup_20261009.jsonl'
AUDIT=ROOT/'evidence/retained_exact_full_version_audit_20261015_v17.json'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def blob(s):return subprocess.check_output(['git','hash-object','--stdin'],input=s.encode()).decode().strip()
def prior(p):return subprocess.check_output(['git','show',BASE+':'+str(p.relative_to(REPO))],text=True)
def rows(s):return [json.loads(x) for x in s.splitlines() if x.strip()]
def read(p):return json.loads(p.read_text())
def run(check=False,historical=False):
    if historical and not check:raise ValueError("historical mode is read-only")
    meta=read(EV/'run.json');acq=read(EV/'acquisition.json')
    assert meta['id']==38638063495 and meta['head_sha']==HEAD
    assert meta['status']=='completed' and meta['conclusion']=='success'
    bank_path=ROOT/'experiments/source_native_closure_v3.jsonl'
    assert sha(bank_path.read_text())==acq['bank_sha256']=='a3fef584fc0bcc9ec06c814b8ee244bf6f663f3fe8a4e113e8026b605eab131e'
    bank=rows(bank_path.read_text());measure=rows((EV/'results.jsonl').read_text())
    assert {(r['name'],r['label']) for r in bank}=={(r['name'],r['candidate_label']) for r in measure}
    before=rows(prior(PORT));packet=prior(PACKET)
    oldaudit=json.loads(prior(ROOT/'evidence/retained_exact_full_version_audit_20261015_v16.json'))
    records=copy.deepcopy(oldaudit['records']);byname={r['name']:r for r in records}
    decisions={};winners={};gain=0.0
    for name in dict.fromkeys(r['name'] for r in bank):
        candidates=[r for r in bank if r['name']==name]
        scores=[]
        for m in measure:
            if m['name']!=name:continue
            c=next(c for c in candidates if c['label']==m['candidate_label'])
            assert m.get('proof_sha256') in (None,sha(c['proof']))
            if c['operator']!='control':assert m['proof_sha256']==sha(c['proof'])
            scores.append(dict(m,proof_sha256=sha(c['proof']),public_harness_sha=PIN,all_versions=True))
        packet,d=reclose_packet(packet,name,candidates,scores,required_versions=byname[name]['required_versions'],expected_public_sha=PIN,incumbent_label='v16_control')
        decisions[name]=d
        if d['objective_gain']<=0:continue
        winner=next(c for c in candidates if c['label']==d['selected_label'])
        score=next(s for s in scores if s['candidate_label']==winner['label'])
        winners[name]=winner;gain+=d['objective_gain']
        rec=byname[name]
        rec.update(label='warranted_'+winner['label'],proof_sha256=sha(winner['proof']),
          measured_objective_sum_pct=score['objective_sum_pct'],compat=score['compat'],
          independent_run=meta['id'],evidence_status='WARRANTED_INDEPENDENT_EXACT_REQUIRED_VERSION',
          independent_authority=dict(run=meta['id'],source_head=HEAD,protected_source_sha=PIN,
            proof_sha256=sha(winner['proof']),required_versions_verified=rec['required_versions'],
            all_required_versions_positive=True,compiled=True,statement_ok=True,
            measured=dict(tokens=score['length'],heartbeats=score['heartbeats'],objective_sum_pct=score['objective_sum_pct'])))
    assert len(winners)==2,'Expected two exact native improvements'
    out=[]
    for line in prior(PORT).splitlines():
        item=json.loads(line)
        if item['name'] in winners:
            w=winners[item['name']];item.update(proof=w['proof'],label='warranted_'+w['label'],
              provenance='Source-acquired local sharing + native failure-location closure; full required-version run38638063495 at5860c364')
            line=json.dumps(item,ensure_ascii=False)
        out.append(line)
    portfolio='\n'.join(out)+'\n';after=rows(portfolio)
    assert len(after)==len(rows(packet))==15
    assert sum(a==b for a,b in zip(before,after))==13
    assert [(r['name'],r['proof']) for r in after]==[(r['name'],r['proof']) for r in rows(packet)]
    for r in after:assert sha(r['proof'])==byname[r['name']]['proof_sha256']
    total=round(oldaudit['projected_score']['objective_sum_total']+gain,2)
    audit=dict(schema='mathgraph.lra.retained-proof-exact-version-audit.v17',state='EXACT_NATIVE_QUALIFIED_PACKET',
      observed_on='2026-10-15',source_repo='aurasoph/lean-refactor',source_sha=PIN,
      previous_audit_path='competitions/lean_refactor_arena/evidence/retained_exact_full_version_audit_20261015_v16.json',
      baseline_commit=BASE,portfolio_path=str(PORT.relative_to(REPO)),portfolio_blob_sha=blob(portfolio),
      current_portfolio_blob_sha=blob(portfolio),records=records,comparator_full_version_exact_count=6,
      independently_qualified_count=9,total_authorized_by_prior_evidence=15,
      change_fingerprint=dict(changed_theorems=list(winners),preserved_proof_rows_from_v16=13,source_run=meta['id'],source_head=HEAD),
      protected_future_invariant='Thirteen V16 rows byte-identical; every proof bound to complete required-version authority.',
      current_packet=dict(path=str(PACKET.relative_to(REPO)),git_blob_sha=blob(packet),sha256=sha(packet),rows=15,status='EXACT_V17_PACKET_RECLOSED'),
      projected_score=dict(objective_sum_total=total,combined_pct_if_full_survival=round((total/15+100)/3,4),
        prospective_delta_points=round(gain/45,6),status='LOCAL_PROJECTION_NOT_HOSTED_SCORE'),
      decisions=decisions,promotion_boundary=dict(official_submission=False,competition_generation_budget='UNKNOWN',
        final_competition_eligibility='UNKNOWN',operator_transfer='FEEDBACK_ASSISTED_PREVIOUSLY_INSPECTED_WARMUPS'))
    pointer=dict(schema='mathgraph.lra.current-audit-pointer.v1',audit_path=str(AUDIT.relative_to(ROOT)),version='V17')
    if check:
        def expected(p):
            if not historical:return p.read_text()
            return subprocess.check_output(['git','show','2b6010d70daba376eab87d83775ab4cc1e16fda7:'+str(p.relative_to(REPO))],text=True)
        assert expected(PORT)==portfolio and expected(PACKET)==packet and json.loads(expected(AUDIT))==audit
        assert json.loads(expected(ROOT/'evidence/retained_current_audit.json'))==pointer
    else:
        PORT.write_text(portfolio);PACKET.write_text(packet)
        AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        (ROOT/'evidence/retained_current_audit.json').write_text(json.dumps(pointer,indent=2)+'\n')
    print(json.dumps(dict(status='V17_QUALIFIED_RECLOSED',changed=2,unchanged=13,packet_sha256=sha(packet),native_objective_gain=gain,projection=audit['projected_score']),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--historical',action='store_true');a=p.parse_args();run(a.check,a.historical)
