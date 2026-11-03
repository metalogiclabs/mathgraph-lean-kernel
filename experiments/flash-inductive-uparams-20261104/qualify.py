"""Paired source-pinned Flash / Arena regression for an inductive universe scope fix.

The candidate is allowed one deliberate verdict improvement: reject the
official Arena `inductive-undeclared-universe` invalid export. All other small-test
verdicts must remain byte-for-byte equivalent at the exit-code boundary.

This is a bounded correctness regression, not a Mathlib performance result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


TARGET = 'inductive-undeclared-universe'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check(binary, config, fixture, timeout):
    try:
        with fixture.open('rb') as stream:
            result = subprocess.run(
                [str(binary), str(config)], stdin=stream,
                capture_output=True, timeout=timeout, check=False)
        return {'rc': result.returncode,
                'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
                'stderr_tail': result.stderr[-300:].decode(errors='replace')}
    except subprocess.TimeoutExpired:
        return {'rc': 'TIMEOUT'}


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument('--before', type=Path, required=True)
    arg.add_argument('--after', type=Path, required=True)
    arg.add_argument('--config', type=Path, required=True)
    arg.add_argument('--fixtures', type=Path, required=True)
    arg.add_argument('--fixture-archive', type=Path, required=True)
    arg.add_argument('--report', type=Path, required=True)
    a = arg.parse_args()

    # Every examined test is provided by the official Arena tarball.
    cases = []
    skipped = []
    for fixture in sorted(a.fixtures.rglob('*.ndjson')):
        parts = fixture.relative_to(a.fixtures).parts
        if not parts or parts[0] not in ('good', 'bad'):
            skipped.append({'case': str(fixture.relative_to(a.fixtures)),
                            'reason': 'not in good/bad directory'})
            continue
        if 'perf' in parts:
            skipped.append({'case': str(fixture.relative_to(a.fixtures)),
                            'reason': 'performance workload excluded from bounded regression'})
            continue
        cases.append((fixture, parts[0]))
    assert cases and any(TARGET in fixture.name for fixture, _ in cases)
    assert len({str(fixture) for fixture, _ in cases}) == len(cases)

    results = []
    for index, (fixture, expected) in enumerate(cases):
        original = check(a.before, a.config, fixture, timeout=60)
        candidate = check(a.after, a.config, fixture, timeout=60)
        identity = str(fixture.relative_to(a.fixtures))
        is_target = TARGET in fixture.name
        is_same = original['rc'] == candidate['rc']
        passes = ((original['rc'] == 0 and candidate['rc'] == 1 and expected == 'bad')
                  if is_target else is_same)
        result = {'case': identity, 'expected': expected,
                  'input_sha256': digest(fixture),
                  'before': original, 'after': candidate,
                  'target': is_target, 'protected': passes}
        results.append(result)
        print('FLASH_PAIR', json.dumps({
            'case': identity, 'before': original['rc'], 'after': candidate['rc'],
            'expected': expected, 'protected': passes}), flush=True)
        # Preserve a partial evidence report even when a case falsifies the
        # expected delta. We never erase negative or UNKNOWN observations.
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps({
            'suite_sha256': digest(a.fixture_archive),
            'before_binary_sha256': digest(a.before),
            'after_binary_sha256': digest(a.after),
            'cases': results, 'skipped': skipped,
            'status': 'INCOMPLETE' if index + 1 < len(cases) else 'EVALUATING',
        }, indent=2) + '\n')
        if not passes:
            break

    all_pass = len(results) == len(cases) and all(r['protected'] for r in results)
    target_rows = [r for r in results if r['target']]
    all_pass = all_pass and len(target_rows) == 1
    report = {
        'status': 'WARRANTED_BOUNDED_SMALL_ARENA_NONREGRESSION' if all_pass else 'REJECTED_OR_INCOMPLETE',
        'qualified': all_pass,
        'suite_sha256': digest(a.fixture_archive),
        'before_binary_sha256': digest(a.before),
        'after_binary_sha256': digest(a.after),
        'test_count': len(cases), 'tested_count': len(results),
        'target': TARGET,
        'target_positive': bool(target_rows and target_rows[0]['protected']),
        'cases': results, 'skipped': skipped,
        'full_mathlib': 'NOT_TESTED', 'performance': 'NOT_TESTED',
        'attribution': 'Independent source-level universe scope check, motivated by ammkrn/nanoda_lib issue #79 and official Lean kernel',
    }
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('FLASH_PROTECTED_SUMMARY', json.dumps({k: v for k, v in report.items()
                                                   if k not in ('cases', 'skipped')}), flush=True)
    if not all_pass:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
