#!/usr/bin/env python3
"""Real accepted-state parity and no-full-export warm-path regression."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import engine
from producer_delta import sources_at
from revision_chain import RevisionChainSession
try:
    from authenticated_state import StateChainSession
except ModuleNotFoundError as error:
    if error.name != 'authenticated_state':
        raise
    StateChainSession = None


def normalized(decisions):
    return [{k:v for k,v in d.items() if k != 'evidence_id'} for d in decisions]


def run(args):
    # Explicit feature assertion yields the preimplementation RED, then the same
    # test executes genuine Lean production and native kernels after it exists.
    assert StateChainSession is not None, 'authenticated state mode is missing'
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    states = sources_at(args.workloads / 'baseline' / 'source')
    source = out / 'source'
    for name, value in states.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    report = dict(passed=False, source_sha=subprocess.check_output(
        ['git','rev-parse','HEAD'],text=True).strip(), steps=[])
    with tempfile.TemporaryDirectory(prefix='state-issuer-') as private:
        key = Path(private) / 'issuer.key'
        key.write_bytes(os.urandom(32));key.chmod(0o600)
        def session(kind, folder):
            return kind(out / folder, args.workloads, args.producer,
                args.binaries / 'check-selected', args.binaries / 'export-index',
                args.binaries / 'index-session', key, sparse_index_wire=True,
                sparse_receipt=True, frozen_baseline=True,
                retained_checker=args.binaries / 'check-selected-retained-session')
        with session(RevisionChainSession,'full-state') as full, session(StateChainSession,'delta-state') as live:
            report['full_ready'],report['state_ready'] = full.start(),live.start()
            for filename,before,after,name in (
                ('IncrementalWorkload/Base.lean','def early : Nat := 17','def early : Nat := 23','early'),
                ('IncrementalWorkload/Leaves.lean','n * n + 3','n * n + 5','unrelated'),
                ('IncrementalWorkload/Base.lean','def early : Nat := 23','def early : Nat := 17','early'),
                ('IncrementalWorkload/Leaves.lean','n * n + 5','n * n + 3','unrelated')):
                file = source / filename
                file.write_text(file.read_text().replace(before,after))
                change=(filename,before,after);names=['IncrementalWorkload.'+name]
                reference = full.apply(source,change,names)
                assert reference['status']=='VERIFIED',reference
                # Instrument an actual full-export syscall; the real Lean and
                # Rust processes continue checking, without mock verdicts.
                with patch('os.memfd_create',side_effect=AssertionError('warm full export was materialized')):
                    actual = live.apply(source,change,names)
                assert actual['status']=='VERIFIED',actual
                assert actual.get('export_sha256') is None, 'state identity masquerades as a file SHA'
                assert actual['state_id'] != reference['export_sha256']
                assert normalized(actual['decisions'])==normalized(reference['decisions'])
                assert actual['counts']==reference['counts']
                assert engine.encoded(live.old['index'])==engine.encoded(full.old['index'])
                assert actual['representation']['full_export_bytes_materialized']==0
                assert actual['representation']['full_export_bytes_hashed']==0
                exported=live.materialize_current()
                assert exported['state_id']==actual['state_id']
                assert exported['export_sha256']==reference['export_sha256']
                raw=Path(exported['path']).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==reference['export_sha256']
                config=out/'fresh-config.json'
                config.write_bytes(engine.encoded(dict(full.old['provenance']['configuration'],
                                                       export_file_path=exported['path'])))
                oracle=subprocess.run([str(args.binaries/'sokonanoda'),str(config)],capture_output=True,timeout=300)
                assert oracle.returncode==0,(oracle.returncode,oracle.stderr)
                audit=live.audit_current_acceptance(full.old['index'])
                report['steps'].append(dict(state_id=actual['state_id'],head=live.head_id,
                    evidence_id=actual['evidence_id'],export_sha256=exported['export_sha256'],
                    export_bytes=len(raw),counts=actual['counts'],fresh_rust_returncode=oracle.returncode,
                    receipt_audit=audit,timings=actual['timings']))
                (out/'partial.json').write_bytes(engine.encoded(report))
            head,evidence,state = live.head_id,live.base_id,live.state_id
            index=engine.encoded(live.old['index'])
        with session(StateChainSession,'delta-state') as cold:
            restarted=cold.start(expected_head=head)
            assert cold.head_id==head and cold.base_id==evidence and cold.state_id==state
            assert engine.encoded(cold.old['index'])==index
            assert restarted['replayed_revisions']==4
            with patch('os.memfd_create',side_effect=AssertionError('unchanged state materialized a full export')):
                unchanged=cold.apply(source,None,[])
            assert unchanged['status']=='VERIFIED' and unchanged['counts']['scheduled']==0
            report.update(cold=restarted,unchanged=unchanged['counts'],passed=True)
    (out/'summary.json').write_bytes(engine.encoded(report))
    print(json.dumps(dict(passed=True,changed_revisions=4,cold_replayed=4,
                          exact_full_export_parity=True,real_full_rust_checks=4)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workloads',type=Path,required=True)
    p.add_argument('--producer',type=Path,required=True)
    p.add_argument('--binaries',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
