#!/usr/bin/env python3
"""Read actual primary receipts and full-index oracle rows; no kernel claim."""
from collections import Counter
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = Path('/workspace/kernel-audit/authenticated-state/ci-cec9941/extracted-compact/artifacts/authenticated-state')
EDITS = ('early-definition', 'unrelated-definition', 'restore-early-definition', 'restore-unrelated-definition')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(profile, state):
    sidecar = ROOT / 'references' / profile / str(state) / 'native' / 'process.stdout.archive.json'
    descriptor = json.loads(sidecar.read_bytes())
    blob = (ROOT / descriptor['artifact_relative_path']).read_bytes()
    assert sha(blob) == descriptor['sha256'] and len(blob) == descriptor['bytes']
    raw = gzip.decompress(blob)
    assert sha(raw) == descriptor['uncompressed_sha256'] and len(raw) == descriptor['uncompressed_bytes']
    return json.loads(raw), dict(sidecar=str(sidecar.relative_to(ROOT)), **descriptor)


def run():
    analysis = json.loads((HERE / 'analysis.json').read_bytes())
    report = dict(schema='mathgraph.authenticated-state.actual-work-kinds.v1',
        source_sha=analysis['source_sha'], summary_sha256=analysis['summary_sha256'], profiles={},
        scope='Classification of checked indices from actual primary authenticated receipt bytes against actual fresh full-index oracle rows. '
            'HMAC tags are observed, not reauthenticated without the private historical key. No new kernel or reuse certification.')
    for profile, observations in analysis['profiles'].items():
        refs = {state: reference(profile, state) for state in (0, 1, 2, 3)}
        cache = ROOT / 'primary' / profile / 'pair-0' / 'state' / 'session' / 'cache'
        heads = {}
        for path in (cache / 'chain').glob('*.json'):
            raw = path.read_bytes()
            assert sha(raw) == path.stem
            value = json.loads(raw)['payload']
            assert value['schema'] == 'mathgraph.lean-accepted-state-chain.v1'
            assert value['revision'] not in heads
            heads[value['revision']] = value
        assert set(heads) == set(range(1, 41))
        result = dict(edits={}, reference_index_archives={str(k): v[1] for k, v in refs.items()},
            fresh_single_Rust_genesis_median_wall_seconds=statistics.median(
                float(pair['arms']['direct']['genesis_command_wall_seconds']) for pair in observations['pairs']))
        for offset, edit in enumerate(EDITS, 1):
            kind_series = []
            for revision in range(offset, 41, 4):
                head = heads[revision]
                path = cache / 'records' / (head['evidence_id'] + '.json')
                raw = path.read_bytes()
                assert sha(raw) == path.stem
                receipt = json.loads(raw)['payload']
                assert receipt['schema'] == 'mathgraph.incremental-lean.state-accepted.v1'
                assert receipt['state_id'] == head['state_id']
                current = refs[(1, 2, 3, 0)[offset - 1]][0]
                selected = receipt['checked_indices']
                assert selected == sorted(set(selected))
                assert receipt['obligation_count'] == current['count']
                kinds = dict(sorted(Counter(current['declarations'][i]['kind'] for i in selected).items()))
                kind_series.append(kinds)
            assert all(item == kind_series[0] for item in kind_series)
            counts = [pair['arms']['state']['updates'][i]['counts'] for pair in observations['pairs']
                      for i in range(offset - 1, 40, 4)]
            assert len(counts) == 50 and all(c == counts[0] for c in counts)
            assert sum(kind_series[0].values()) == counts[0]['rechecked']
            result['edits'][edit] = dict(counts=counts[0], checked_by_kind=kind_series[0],
                cycles_classified_from_actual_receipts=10, actual_count_observations_agreeing=50)
        report['profiles'][profile] = result
    (HERE / 'work-kind-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({p: {'single_Rust_genesis_median': v['fresh_single_Rust_genesis_median_wall_seconds'],
        'edits': v['edits']} for p, v in report['profiles'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, default=ROOT,
                        help='Recreated exact authenticated-state artifact subtree.')
    ROOT = parser.parse_args().benchmark.resolve()
    run()
