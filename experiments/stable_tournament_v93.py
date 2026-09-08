#!/usr/bin/env python3
"""Run the unchanged v93 candidates with bounded, evidence-preserving brackets."""
import json
import math
import sys
from pathlib import Path
import full_corpus_tournament_v93 as t

ARCHIVE_RUN = 34269495716
PINNED = {
    'init-prelude': 'fc440bd35aa4ecb244836eef0c2e31c578ac4460f42665f4e8305cbc2cd2104d',
    'cedar': '2c8fb847551e7a6d0c3c1aed376b0422c51979b4d4995447957cb9d986b72339',
    'mathlib': 'ca2ec20fd063b61e71867b2975c81bd989af9f879b4886b8f08cd23c767a47bb',
}
FIXTURE_ID = '71ff2f09375135ddec266c910ac1ffe1beafc88cdd740e6c23e43f3635fd3a31'
MAX_ATTEMPTS = 3
MAX_DRIFT_PERCENT = 5.0
BLOCK_SIZE = 2

class UnstableBenchmark(Exception):
    pass


def verify_archive():
    fixtures = t.ROOT / 'fixtures'
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    inputs, identity = t.select_fixtures(manifest)
    assert inputs == PINNED and identity == FIXTURE_ID, 'Wrong archived fixture set'
    for corpus, expected in PINNED.items():
        path = fixtures / (corpus + '.ndjson')
        assert path.is_file() and t.v.sha_file(path) == expected, 'Archived input mismatch: ' + corpus
    t.r.EXPECTED = dict(PINNED)
    return identity


def setup():
    identity = verify_archive()
    original_setup()
    assert t.FROZEN == PINNED
    assert json.loads((t.OUT / 'source.json').read_text())['fixture_set_id'] == identity
    print('V93_ARCHIVED_FIXTURES=PASS', flush=True)


def checked_run(binary, corpus, tag, reference=None):
    row = t.v.run_binary(binary, corpus, tag)
    assert row['rc'] == 0, 'Checker failed: ' + tag
    output = (row['stdout_sha256'], row['stderr_sha256'])
    if reference is not None:
        assert output == reference, 'Replay mismatch: ' + tag
    return row, output


def measure_block(binaries, names, corpus, tag):
    before, reference = checked_run(binaries['control']['path'], corpus, tag + '.before')
    pending = []
    for name in names:
        row, _ = checked_run(binaries[name]['path'], corpus, tag + '.' + name, reference)
        pending.append((name, row))
    after, _ = checked_run(binaries['control']['path'], corpus, tag + '.after', reference)
    baseline = (before['seconds'] + after['seconds']) / 2
    drift = abs(after['seconds'] / before['seconds'] - 1) * 100
    accepted = drift <= MAX_DRIFT_PERCENT
    record = {'corpus': corpus, 'tag': tag, 'names': list(names), 'accepted': accepted,
              'drift_percent': drift, 'control_before': before, 'control_after': after,
              'candidates': {name: row for name, row in pending}}
    rows = [{'arm': name, 'corpus': corpus, 'ratio': row['seconds'] / baseline,
             'baseline_seconds': baseline, 'control_before': before,
             'control_after': after, 'candidate': row} for name, row in pending] if accepted else []
    return record, rows


def race(binaries, names, phase, passes, summary):
    rows = []
    attempts = []
    for corpus in t.CORPORA:
        for i in range(passes):
            order = list(names) if i % 2 == 0 else list(reversed(names))
            for start in range(0, len(order), BLOCK_SIZE):
                block = order[start:start + BLOCK_SIZE]
                accepted = False
                for retry in range(MAX_ATTEMPTS):
                    tag = f'{phase}.{corpus}.{i}.{start}.{retry}'
                    record, measured = measure_block(binaries, block, corpus, tag)
                    attempts.append(record)
                    for row in measured:
                        row['pass'] = i
                    rows.extend(measured)
                    complete = [n for n in names if all(any(x['arm'] == n and x['corpus'] == c for x in rows) for c in t.CORPORA)]
                    summary[phase] = {'rows': rows, 'attempts': attempts, 'scores': t.score(rows, complete)}
                    t.save(summary)
                    if record['accepted']:
                        accepted = True
                        break
                if not accepted:
                    raise UnstableBenchmark('Control drift exceeded 5% on three brackets: ' + corpus)
        print('V93_' + phase.upper() + '_' + corpus.upper() + '=COMPLETE', flush=True)
    return t.score(rows, names), rows


def self_test():
    original = t.v.run_binary
    try:
        def fake(times, mismatch=False):
            values = iter(times)
            def run(binary, corpus, tag):
                seconds = next(values)
                return {'rc': 0, 'seconds': seconds,
                        'stdout_sha256': 'wrong' if mismatch and binary == 'candidate' else 'same',
                        'stderr_sha256': 'same'}
            return run
        binaries = {'control': {'path': 'control'}, 'candidate': {'path': 'candidate'}}
        t.v.run_binary = fake([10, 9, 12])
        record, rows = measure_block(binaries, ['candidate'], 'cedar', 'test')
        assert not record['accepted'] and not rows and record['drift_percent'] > 5
        t.v.run_binary = fake([10, 9, 10])
        record, rows = measure_block(binaries, ['candidate'], 'cedar', 'test')
        assert record['accepted'] and len(rows) == 1 and abs(rows[0]['ratio'] - .9) < 1e-12
        t.v.run_binary = fake([10, 9, 10], mismatch=True)
        try:
            measure_block(binaries, ['candidate'], 'cedar', 'test')
        except AssertionError as exc:
            assert 'Replay mismatch' in str(exc)
        else:
            raise AssertionError('Replay mismatch was accepted')
        assert t.score([dict(rows[0], corpus=c) for c in t.CORPORA], ['candidate'])['candidate']['geomean_delta_percent'] < -9.9
        print('V93_STABLE_BRACKET_SELF_TEST=PASS', flush=True)
    finally:
        t.v.run_binary = original


original_setup = t.setup

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        self_test()
    else:
        t.setup = setup
        t.race = race
        try:
            t.main()
        except UnstableBenchmark as exc:
            summary = json.loads((t.OUT / 'summary.json').read_text())
            summary.update(status='COMPLETE', decision='INCONCLUSIVE_CONTROL_DRIFT', release_promoted=False)
            summary['diagnostic'] = str(exc)
            summary.pop('error', None)
            t.save(summary)
            print('V93_DECISION=INCONCLUSIVE_CONTROL_DRIFT', flush=True)
            print('V93_RELEASE_PROMOTED=false', flush=True)
