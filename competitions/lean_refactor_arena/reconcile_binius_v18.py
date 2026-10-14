#!/usr/bin/env python3
"""Reclose completed source-acquisition native evidence using existing admission.

V17 bytes remain immutable in git/official receipt. Only positively qualified
native improvements enter V18. This does not establish hosted scoring or budget.
"""
import argparse,copy,hashlib,json,pathlib,subprocess
from frontier_reclose import reclose_packet
from version_evidence_merge import merge_versions
ROOT=pathlib.Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE='2b6010d70daba376eab87d83775ab4cc1e16fda7'
HEAD='d241190ef46775abc152c393d389db406fb08cf3'
PIN='7f3a401470d04f70013d293db4253b088ec8a0ae'
EV=ROOT/'evidence/binius_source_transfer_v4'
PORT=ROOT/'portfolio/warmup_portfolio_v1.jsonl'
PACKET=ROOT/'submissions/mathgraph_verified_15_warmup_20261009.jsonl'
AUDIT=ROOT/'evidence/retained_exact_full_version_audit_20261015_v18.json'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def blob(s):return subprocess.check_output(['git','hash-object','--stdin'],input=s.encode()).decode().strip()
def prior(p):return subprocess.check_output(['git','show',BASE+':'+str(p.relative_to(REPO))],text=True)
def rows(s):return [json.loads(x) for x in s.splitlines() if x.strip()]
def read(p):return json.loads(p.read_text())
def run(check=False):
    meta=read(EV/'qualification-run.json');primary_meta=read(EV/'run.json')
    assert meta['id']==38645914725 and meta['head_sha']==HEAD
    assert meta['status']=='completed' and meta['conclusion']=='success'
    assert primary_meta['run_id']==38643866166 and primary_meta['native_run_conclusion']=='success'
    assert primary_meta['source_commit']=='0e510afad3dbff777bb79bc74f554cc50b14b65c'
    assert primary_meta['bank_sha256']==sha((ROOT/'experiments/source_binius_transfer_v4.jsonl').read_text())
    bank=rows((ROOT/'experiments/binius_fold_qualification_v4.jsonl').read_text())
    assert len(bank)==2 and {r['name'] for r in bank}=={'Binius.BinaryBasefold.fold_advances_evaluation_poly'}
    native_bank=rows((ROOT/'experiments/source_binius_transfer_v4.jsonl').read_text())
    assert all(r in native_bank for r in bank)
    primary_path=EV/'results.jsonl'
    assert primary_path.read_text()==subprocess.check_output(['git','show',HEAD+':'+str(primary_path.relative_to(REPO))],text=True)
    primary=rows(primary_path.read_text())
    older=[]
    for version in ['v4.30','v4.29']:
        path=EV/('compatibility-'+version+'.jsonl')
        assert sha(path.read_text())==meta['evidence_sha256'][path.name]
        values=rows(path.read_text())
        assert len(values)==2
        assert {(r['name'],r['candidate_label']) for r in values}=={(r['name'],r['label']) for r in bank}
        assert all(set(r['compat'])=={version+'.0'} for r in values)
        older.extend(values)
    measure=[]
    for c in bank:
        p=next(r for r in primary if (r['name'],r['candidate_label'])==(c['name'],c['label']))
        assert set(p['compat'])=={'v4.31.0'}
        others=[r for r in older if (r['name'],r['candidate_label'])==(c['name'],c['label'])]
        measure.append(merge_versions(p,others,['v4.31.0','v4.30.0','v4.29.0']))
    before=rows(prior(PORT));packet=prior(PACKET)
    oldaudit=json.loads(prior(ROOT/'evidence/retained_exact_full_version_audit_20261015_v17.json'))
    records=copy.deepcopy(oldaudit['records']);byname={r['name']:r for r in records}
    decisions={};winners={};gain=0.0
    for name in dict.fromkeys(r['name'] for r in bank):
        candidates=[r for r in bank if r['name']==name]
        scores=[]
        for m in measure:
            if m['name']!=name:continue
            c=next(c for c in candidates if c['label']==m['candidate_label'])
            assert m['proof_sha256']==sha(c['proof']) and m['public_harness_sha']==PIN
            scores.append(m)
        packet,d=reclose_packet(packet,name,candidates,scores,required_versions=byname[name]['required_versions'],expected_public_sha=PIN,incumbent_label='v17_control')
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
            all_required_versions_positive=True,compiled=True,statement_ok=True,primary_run=38643866166,primary_source_head=primary_meta['source_commit'],
            measured=dict(tokens=score['length'],heartbeats=score['heartbeats'],objective_sum_pct=score['objective_sum_pct'])))
    assert len(winners)==1,'Expected one exact native improvement'
    out=[]
    for line in prior(PORT).splitlines():
        item=json.loads(line)
        if item['name'] in winners:
            w=winners[item['name']];item.update(proof=w['proof'],label='warranted_'+w['label'],
              provenance='Unchanged source-local-sharing-v2 generator; primary run38643866166 and exact older-version qualification run38645914725')
            line=json.dumps(item,ensure_ascii=False)
        out.append(line)
    portfolio='\n'.join(out)+'\n';after=rows(portfolio)
    assert len(after)==len(rows(packet))==15
    assert sum(a==b for a,b in zip(before,after))==14
    assert [(r['name'],r['proof']) for r in after]==[(r['name'],r['proof']) for r in rows(packet)]
    for r in after:assert sha(r['proof'])==byname[r['name']]['proof_sha256']
    total=round(oldaudit['projected_score']['objective_sum_total']+gain,2)
    audit=dict(schema='mathgraph.lra.retained-proof-exact-version-audit.v18',state='EXACT_NATIVE_QUALIFIED_PACKET',
      observed_on='2026-10-15',source_repo='aurasoph/lean-refactor',source_sha=PIN,
      previous_audit_path='competitions/lean_refactor_arena/evidence/retained_exact_full_version_audit_20261015_v17.json',
      baseline_commit=BASE,portfolio_path=str(PORT.relative_to(REPO)),portfolio_blob_sha=blob(portfolio),
      current_portfolio_blob_sha=blob(portfolio),records=records,comparator_full_version_exact_count=6,
      independently_qualified_count=9,total_authorized_by_prior_evidence=15,
      change_fingerprint=dict(changed_theorems=list(winners),preserved_proof_rows_from_v17=14,source_run=meta['id'],source_head=HEAD),
      protected_future_invariant='Fourteen V17 rows byte-identical; every proof bound to complete required-version authority.',
      current_packet=dict(path=str(PACKET.relative_to(REPO)),git_blob_sha=blob(packet),sha256=sha(packet),rows=15,status='EXACT_V18_PACKET_RECLOSED'),
      projected_score=dict(objective_sum_total=total,combined_pct_if_full_survival=round((total/15+100)/3,4),
        prospective_delta_points=round(gain/45,6),status='LOCAL_PROJECTION_NOT_HOSTED_SCORE'),
      decisions=decisions,promotion_boundary=dict(official_submission=False,competition_generation_budget='UNKNOWN',
        final_competition_eligibility='UNKNOWN',operator_transfer='FEEDBACK_ASSISTED_PREVIOUSLY_INSPECTED_WARMUPS'))
    pointer=dict(schema='mathgraph.lra.current-audit-pointer.v1',audit_path=str(AUDIT.relative_to(ROOT)),version='V18')
    if check:
        assert PORT.read_text()==portfolio and PACKET.read_text()==packet and read(AUDIT)==audit
        assert read(ROOT/'evidence/retained_current_audit.json')==pointer
    else:
        PORT.write_text(portfolio);PACKET.write_text(packet)
        AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        (ROOT/'evidence/retained_current_audit.json').write_text(json.dumps(pointer,indent=2)+'\n')
    print(json.dumps(dict(status='V18_QUALIFIED_RECLOSED',changed=1,unchanged=14,packet_sha256=sha(packet),native_objective_gain=gain,projection=audit['projected_score']),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');run(p.parse_args().check)
