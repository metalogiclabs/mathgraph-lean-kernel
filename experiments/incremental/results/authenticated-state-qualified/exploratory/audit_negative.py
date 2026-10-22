#!/usr/bin/env python3
"""Independently full-index/check the exact persisted failed-precondition input.

No cache entry is accepted here. The construction is only an actual-input
witness and genuine fresh Rust makes the kernel acceptance decision.
"""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
import probe
from authenticated_state import ExportRecipe
from qualify_delta import independent_partition, audit_partition

def sha(data):return hashlib.sha256(data).hexdigest()
def read_blob(ref):
    raw=Path(ref['path']).read_bytes();assert sha(raw)==ref['sha256']
    data=gzip.decompress(raw)
    assert len(data)==ref['uncompressed_bytes'] and sha(data)==ref['uncompressed_sha256']
    return data
def main():
    report=json.loads((ROOT/'summary.json').read_bytes())
    assert report['qualified'] is False and report['passed'] is False
    assert report['source_sha']==probe.EXPECTED
    assert report['input_pins_unchanged'] and report['source_worktree_clean']
    # The exploratory driver reused its local `before` variable for the source
    # patch, so its final source_closure_unchanged comparison was string==dict.
    # Preserve that original false field; independently compare the actual
    # complete preflight file/hash mapping here instead of rewriting history.
    assert {p:sha((probe.REPO/p).read_bytes()) for p in report['source_closure']}==report['source_closure']
    step=report['steps'][-1];assert step['profile']=='expanded11653' and step['revision']==1
    result=json.loads(read_blob(step['result']))
    baseline_index=json.loads(read_blob(report['profiles']['expanded11653']['baseline_index']['stdout']))
    cache=ROOT/'expanded11653/session/cache'
    receipt_raw=(cache/'records'/(result['evidence_id']+'.json')).read_bytes()
    assert sha(receipt_raw)==result['evidence_id']
    receipt=json.loads(receipt_raw)['payload']
    representation_raw=(cache/'representations'/(result['state_id']+'.json')).read_bytes()
    assert sha(representation_raw)==result['state_id']
    representation=json.loads(representation_raw)
    delta_raw=(cache/'deltas'/(representation['delta_sha256']+'.ndjson')).read_bytes()
    assert sha(delta_raw)==representation['delta_sha256']
    transition_raw=(cache/'transitions'/(representation['transition_id']+'.json')).read_bytes()
    assert sha(transition_raw)==representation['transition_id']
    transition=json.loads(transition_raw)['payload']
    assert transition['delta_sha256']==representation['delta_sha256']
    assert transition['changed_names']==[probe.NAME]
    assert receipt['state_id']==result['state_id'] and receipt['parent_state_id']==representation['parent_state_id']
    baseline=probe.PROFILES['expanded11653']/'baseline/export.ndjson'
    baseline_raw=baseline.read_bytes()
    assert sha(baseline_raw)==report['input_pins'][str(baseline)]==representation['genesis_export_sha256']
    recipe=ExportRecipe.from_baseline(baseline_raw).append(delta_raw,[probe.NAME])
    actual=ROOT/'negative-audit'/'actual-expanded.ndjson'
    actual.parent.mkdir(exist_ok=True)
    with actual.open('wb') as handle:
        for chunk in recipe.iter_chunks(): handle.write(chunk)
    actual_sha=sha(actual.read_bytes())
    assert actual.stat().st_size==recipe.byte_count==result['representation']['export_bytes']
    stdout,index_run=probe.run_fresh(probe.FRESH/'export-index',actual,ROOT/'negative-audit'/'full-index')
    current=json.loads(stdout)
    from producer_delta import reconstruct_index_patch
    assert probe.engine.encoded(current)==probe.engine.encoded(reconstruct_index_patch(baseline_index,result['typed_update']['index_patch']))
    assert current['meta']==baseline_index['meta']
    assert current['builtins']==baseline_index['builtins']
    assert current['complex']==baseline_index['complex']
    assert current['schedule']==baseline_index['schedule']
    assert [r['deps'] for r in current['declarations']]==[r['deps'] for r in baseline_index['declarations']]
    changed_own=[r for old,r in zip(baseline_index['declarations'],current['declarations']) if old['own']!=r['own']]
    changed_closure=[r for old,r in zip(baseline_index['declarations'],current['declarations']) if old['closure']!=r['closure']]
    assert [r['name'] for r in changed_own]==[probe.NAME]
    assert [r['name'] for r in changed_closure]==[probe.NAME]
    selected,reused=independent_partition(baseline_index,current)
    assert selected==receipt['checked_indices']
    partition=audit_partition(result,baseline_index,current)
    _,kernel_run=probe.run_fresh(probe.FRESH/'sokonanoda',actual,ROOT/'negative-audit'/'fresh-rust')
    assert sha(actual.read_bytes())==actual_sha
    decisions={d['index']:d for d in result['decisions']}
    extra=[]
    for index in selected:
        row=current['declarations'][index]
        old=baseline_index['declarations'][index]
        if row['name']==probe.NAME:continue
        assert row==old
        assert row['kind'] not in ('axiom','def','thm','opaque')
        extra.append(dict(declaration=row,decision=decisions[index]))
    assert len(extra)==len(selected)-1
    audit=dict(schema='mathgraph.local-exploratory.equal-cone-refusal-audit.v1',
        passed=True,qualified=False,scope='LOCAL EXPLORATORY ONLY. Benchmark precondition failed; no scaling claim.',
        source_sha=probe.EXPECTED,probe_source_sha256=sha((ROOT/'probe.py').read_bytes()),
        audit_source_sha256=sha(Path(__file__).read_bytes()),
        baseline_export_sha256=sha(baseline_raw),delta_sha256=sha(delta_raw),
        actual_export_sha256=actual_sha,actual_export_bytes=actual.stat().st_size,
        full_index=index_run,fresh_rust=kernel_run,partition_audit=partition,
        count=current['count'],changed_own=changed_own,changed_closure=changed_closure,
        selected=len(selected),reused=len(reused),native_checked=result['native_kernel_report']['checked'],
        retained_graph_used=result['typed_update']['retained_graph_used'],
        recomputed_sccs=result['typed_update']['recomputed_sccs'],
        all_dependency_edges_unchanged=True,schedule_unchanged=True,globals_unchanged=True,
        extra_selected_unchanged_complex=extra,
        source_owned_local_declarations=[r for r in current['declarations'] if r['name'].startswith('IncrementalWorkload.')],
        reason='Only leaf own/closure identity changes, but every later non-simple obligation loses the exact verified-prefix warrant. Local dependency reuse applies only to axiom/def/thm/opaque.',
        hmac_scope='Live adapter authenticated and signed the accepted input; ephemeral issuer key is deliberately not retained. This post-run audit verifies content-address/linkage/full-index/partition/fresh-kernel, and does not independently reassert HMAC authority.',
        code_pins={p:sha((probe.REPO/'experiments/incremental'/p).read_bytes()) for p in ['engine.py','qualify_delta.py','authenticated_state.py','producer_delta.py','revision_chain.py']})
    audit['probe_observability_bug']='Exploratory driver variable before was overwritten by the source patch string. Its false source_closure_unchanged flag is preserved; this audit independently verified the complete recorded preflight mapping against actual source bytes.'
    audit['source_closure_independently_unchanged']=True
    audit['exact_export_archive']=probe.archive(actual.read_bytes(),'ndjson')
    assert read_blob(audit['exact_export_archive'])==actual.read_bytes()
    actual.unlink() # Own temporary duplicate, preserved losslessly after full oracles.
    probe.write(ROOT/'negative-audit'/'summary.json',audit)
    print(json.dumps({k:audit[k] for k in ['passed','qualified','count','selected','reused','native_checked','recomputed_sccs','all_dependency_edges_unchanged','actual_export_sha256']}))

if __name__=='__main__':main()
