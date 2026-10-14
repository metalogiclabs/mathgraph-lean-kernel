#!/usr/bin/env python3
"""Reclose two completed source-bound Lean results into the V15 portfolio.

This checks archived evidence and unchanged bytes; it does not run Lean or
establish official scoring, generation-budget compliance, or final eligibility.
"""
import argparse
import copy
import hashlib
import json
import pathlib
import subprocess

from arena_upload import forbidden_reason

ROOT = pathlib.Path(__file__).resolve().parent
EV = ROOT / 'evidence/reconcile_v16_20261015'
BASE = '9930906c8aba578cd4e1a08c67d023fdfcb7aa59'
PIN = '7f3a401470d04f70013d293db4253b088ec8a0ae'
PORT = ROOT / 'portfolio/warmup_portfolio_v1.jsonl'
PACKET = ROOT / 'submissions/mathgraph_verified_15_warmup_20261009.jsonl'
AUDIT = ROOT / 'evidence/retained_exact_full_version_audit_20261015_v16.json'


def digest(proof):
    return hashlib.sha256(proof.encode()).hexdigest()


def qualify(proof, expected_hash, score, versions):
    req = set(versions)
    per = score.get('per_version', [])
    valid = (digest(proof['proof']) == expected_hash
        and proof['name'] == score['name']
        and not forbidden_reason(proof['proof'])
        and all(score.get(k) is True for k in ['compiled', 'statement_ok', 'eligible'])
        and not any(score.get(k) for k in ['forbidden', 'untested', 'extra_toplevel_decls'])
        and score.get('survival_pct') == 100
        and score.get('compat') == {v: True for v in req}
        and len(per) == len(req)
        and {v.get('version') for v in per} == req
        and all(v.get('tested') is True and v.get('ok') is True and not v.get('errors') for v in per))
    if not valid:
        raise ValueError('Unqualified proof/hash/version result')


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def baseline(path):
    rel = path.relative_to(ROOT.parents[1])
    return subprocess.check_output(['git', 'show', BASE + ':' + str(rel)], text=True)


def blob(path):
    return subprocess.check_output(['git', 'hash-object', str(path)], text=True).strip()


def run(check=False):
    prior = json.loads(baseline(ROOT / 'evidence/retained_exact_full_version_audit_20261010_v15.json'))
    before = [json.loads(s) for s in baseline(PORT).splitlines() if s.strip()]
    fiber, fs, fscore = read(EV / 'fiber_proof.json'), read(EV / 'fiber_source.json'), read(EV / 'fiber_winner.json')
    wick = rows(EV / 'wick_winner.jsonl')[0]
    ws, wr = read(EV / 'wick_source.json'), read(EV / 'wick_result.json')
    wscore = next(x for x in rows(EV / 'wick_scores.jsonl') if x['candidate_label'] == wick['label'])
    assert fs['pinned_harness'] == ws['harness_pin'] == prior['source_sha'] == PIN
    assert fs['winner_sha256'] == 'c6b953c0027a8d3e9b44889951dbb8177a3841187004684f7104d0d7d30f1c8e'
    assert ws['candidates'][wick['label']] == '0311a7be0df0fbbc727ff635c0dffabed4ead756c5a7bfbbc64157fcc0915a64'
    qualify(fiber, fs['winner_sha256'], fscore, fs['required_versions'])
    qualify(wick, ws['candidates'][wick['label']], wscore, ws['protected_versions'])
    fq = read(EV / 'fiber_qualification.json')
    assert fq['source'] == fs and fq['winner']['objective'] == fscore['objective_sum_pct']
    assert wr['best']['sha256'] == digest(wick['proof'])
    run_meta = read(EV / 'runs.json')
    for key, head in [('fiber', '9d60c7cbe3f0815370d1e53119dd71e84e9dd163'), ('wick', '843ba99aa090ca22cf7245c7b8e404e40d33e5b7')]:
        assert run_meta[key]['head_sha'] == head
        assert run_meta[key]['status'] == 'completed' and run_meta[key]['conclusion'] == 'success'
    old = {x['name']: x for x in before}
    assert digest(old[fiber['name']]['proof']) == fs['reference_sha256']
    assert digest(old[wick['name']]['proof']) == ws['active_proof_sha256']
    scores = {fiber['name']: fscore, wick['name']: wscore}
    incumbent_scores = {fiber['name']: fq['active_incumbent']['objective'], wick['name']: wr['control']['objective']}
    proofs = {fiber['name']: fiber, wick['name']: wick}
    after, audit = copy.deepcopy(before), copy.deepcopy(prior)
    for item in after:
        if item['name'] in proofs:
            p = proofs[item['name']]
            item.update(proof=p['proof'], label='warranted_' + p['label'],
                provenance='Exact source-bound required-version results reclosed 2026-10-15; no new Lean replay')
    assert len(after) == len({x['name'] for x in after}) == 15
    assert sum(x == y for x, y in zip(before, after)) == 13
    for rec in audit['records']:
        item = next(x for x in after if x['name'] == rec['name'])
        rec['proof_sha256'] = digest(item['proof'])
        if rec['name'] in proofs:
            score = scores[rec['name']]
            assert score['objective_sum_pct'] > incumbent_scores[rec['name']]
            if 'measured_objective_sum_pct' in rec:
                assert rec['measured_objective_sum_pct'] == incumbent_scores[rec['name']]
            run_id = 38011591819 if rec['name'] == fiber['name'] else 38011784477
            rec.update(label=item['label'], matches_pinned_public_full_test=False,
                public_hash=None, public_compat=None,
                evidence_status='WARRANTED_INDEPENDENT_EXACT_REQUIRED_VERSION',
                independent_run=run_id, compat=score['compat'],
                independent_authority={'run': run_id, 'proof_sha256': digest(item['proof']),
                    'required_versions_verified': rec['required_versions'], 'all_required_versions_positive': True},
                measured_objective_sum_pct=score['objective_sum_pct'])
    audit.update(schema='mathgraph.lra.retained-proof-exact-version-audit.v16', observed_on='2026-10-15',
        previous_audit_path=str((ROOT / 'evidence/retained_exact_full_version_audit_20261010_v15.json').relative_to(ROOT.parents[1])),
        previous_audit_portfolio_blob=prior['portfolio_blob_sha'], comparator_full_version_exact_count=6,
        independently_qualified_count=9,
        protected_future_invariant='Thirteen V15 rows byte-identical; six external and nine independent exact required-version authorities; no new Lean replay.',
        change_fingerprint={'changed_theorems': list(proofs), 'preserved_proof_rows_from_v15': 13,
            'source_runs': {'fiber': 38011591819, 'wick': 38011784477}, 'baseline_sha': BASE},
        current_version_alias='V16: Binius quotient observer V12 + Wick observer V16; thirteen V15 rows unchanged',
        targeted_reclosure_CI={'reuses_completed_lean_evidence': True, 'fresh_lean_replay': False},
        promotion_boundary={'status': 'EXACT_PACKET_RECLOSED_FROM_COMPLETED_SOURCE_EVIDENCE',
            'official_submission': False, 'competition_generation_budget': 'UNKNOWN_REQUIRES_REPRODUCIBLE_HARNESS_REVIEW'})
    audit['independently_qualified'] = [x for x in prior['independently_qualified'] if x['name'] not in proofs]
    for name, score in scores.items():
        audit['independently_qualified'].append({'name': name, 'run': 38011591819 if name == fiber['name'] else 38011784477,
            'qualification': 'Exact source hash and all required versions positive; archived result reused'})
    audit['warranted_frontier']['Wick'].update(label='warranted_' + wick['label'], run=38011784477,
        length=wscore['length'], heartbeats=wscore['heartbeats'], objective=wscore['objective_sum_pct'], source_label=wick['label'])
    audit['warranted_frontier']['Binius_fiberwise'] = {'label': 'warranted_' + fiber['label'], 'run': 38011591819,
        'length': fscore['length'], 'heartbeats': fscore['heartbeats'], 'objective': fscore['objective_sum_pct'],
        'required_versions': fs['required_versions']}
    total = round(prior['projected_score']['objective_sum_total'] + sum(scores[n]['objective_sum_pct'] - incumbent_scores[n] for n in scores), 2)
    audit['projected_score'] = {'objective_sum_total': total, 'combined_pct_if_full_survival': round((total / 15 + 100) / 3, 4),
        'status': 'PROJECTED__NOT_OFFICIALLY_SUBMITTED', 'leader_comparison': 'Historical leader superseded; official comparison required'}
    expected_packet = [{'name': x['name'], 'proof': x['proof']} for x in after]
    if not check:
        old_port_lines = {json.loads(s)['name']: s for s in baseline(PORT).splitlines() if s.strip()}
        old_packet_lines = {json.loads(s)['name']: s for s in baseline(PACKET).splitlines() if s.strip()}
        PORT.write_text(''.join((json.dumps(x, ensure_ascii=False) if x['name'] in proofs else old_port_lines[x['name']]) + '\n' for x in after))
        PACKET.write_text(''.join((json.dumps(x, ensure_ascii=False) if x['name'] in proofs else old_packet_lines[x['name']]) + '\n' for x in expected_packet))
    assert rows(PORT) == after and rows(PACKET) == expected_packet
    audit['portfolio_blob_sha'] = audit['current_portfolio_blob_sha'] = blob(PORT)
    audit['current_packet'] = {'path': str(PACKET.relative_to(ROOT.parents[1])), 'git_blob_sha': blob(PACKET),
        'rows': 15, 'status': 'EXACT_V16_PACKET_RECLOSED', 'sha256': hashlib.sha256(PACKET.read_bytes()).hexdigest()}
    if check:
        assert read(AUDIT) == audit, 'Stale or changed V16 audit'
    else:
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'state': 'EXACT_PACKET_RECLOSED_FROM_ARCHIVED_LEAN_RESULTS',
        'projected_score': audit['projected_score'], 'packet': audit['current_packet'], 'unchanged_rows': 13}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    run(parser.parse_args().check)
