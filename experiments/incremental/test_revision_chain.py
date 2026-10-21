#!/usr/bin/env python3
"""Real producer/kernel predecessor-chain acceptance and cold-replay smoke test."""
import argparse
import json
import os
from pathlib import Path
import tempfile

import engine
from producer_delta import DeltaSession, SOURCES, sources_at


def run(args):
    if args.legacy_red:
        Session = DeltaSession
    else:
        from revision_chain import RevisionChainSession
        Session = RevisionChainSession
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chain-authority-') as private:
        key = Path(private) / 'issuer.key'
        key.write_bytes(os.urandom(32))
        key.chmod(0o600)
        sources = sources_at(args.workloads / 'baseline' / 'source')
        source = out / 'source'
        for name, text in sources.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        def session():
            return Session(out / 'state', args.workloads, args.producer,
                           args.binaries / 'check-selected', args.binaries / 'export-index',
                           args.binaries / 'index-session', key,
                           sparse_index_wire=True, sparse_receipt=True,
                           frozen_baseline=True,
                           retained_checker=args.binaries / 'check-selected-retained-session')
        results = []
        with session() as live:
            ready = live.start()
            for filename, before, after, name in (
                ('IncrementalWorkload/Base.lean', 'def early : Nat := 17', 'def early : Nat := 23', 'early'),
                ('IncrementalWorkload/Leaves.lean', 'n * n + 3', 'n * n + 5', 'unrelated'),
                ('IncrementalWorkload/Base.lean', 'def early : Nat := 23', 'def early : Nat := 17', 'early'),
                ('IncrementalWorkload/Leaves.lean', 'n * n + 5', 'n * n + 3', 'unrelated')):
                path = source / filename
                path.write_text(path.read_text().replace(before, after))
                result = live.apply(source, (filename, before, after), ['IncrementalWorkload.' + name])
                results.append(result)
                (out / 'partial.json').write_bytes(engine.encoded(dict(ready=ready, results=results)))
                assert result['status'] == 'VERIFIED', result
                assert 0 < result['counts']['scheduled'] < result['counts']['total'], result['counts']
            head, evidence = live.head_id, live.base_id
            expected_index = engine.encoded(live.old['index'])
        with session() as cold:
            restarted = cold.start(expected_head=head)
            assert cold.head_id == head and cold.base_id == evidence
            assert engine.encoded(cold.old['index']) == expected_index
            assert restarted['replayed_revisions'] == 4
            result = cold.apply(source, None, [])
            assert result['status'] == 'VERIFIED' and result['counts']['scheduled'] == 0, result
        import subprocess
        report = dict(passed=True, source_sha=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                      ready=ready, results=results, cold=restarted)
        (out / 'summary.json').write_bytes(engine.encoded(report))
        print(json.dumps(dict(passed=True, revisions=4, cold_replayed=4, head=head)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workloads', type=Path, required=True)
    p.add_argument('--producer', type=Path, required=True)
    p.add_argument('--binaries', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--legacy-red', action='store_true')
    run(p.parse_args())
