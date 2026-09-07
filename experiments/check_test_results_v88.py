#!/usr/bin/env python3
"""Fail-closed comparison of complete Rust unit-test summaries and failures."""
import json
import re
import sys
from pathlib import Path

EXPECTED = {
    'tests::util::reject_rec_rule_with_forged_lambda_domains',
    'tests::util::reject_unlisted_recursor',
}
SUMMARY = re.compile(r'test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out;')
FAILED_NAME = re.compile(r'^    (\S+)$', re.M)

def parse(text, expected_count):
    # Rust captures test output by default. The summary is authoritative even
    # when an older --nocapture log has interleaved progress messages.
    starts = re.findall(r'^running (\d+) tests?\s*$', text, re.M)
    summaries = list(SUMMARY.finditer(text))
    assert starts and summaries and len(starts) == len(summaries), 'incomplete test output'
    assert int(starts[0]) == expected_count, (starts[0], expected_count)
    counts = [tuple(map(int, m.groups()[1:])) for m in summaries]
    passed, failed, ignored, measured, filtered = counts[0]
    assert passed + failed + ignored + measured == expected_count, counts[0]
    assert ignored == measured == filtered == 0
    assert all(m.group(1) == 'ok' and int(m.group(3)) == 0 for m in summaries[1:]), 'non-library test failure'
    # The final failures block is emitted by libtest, not by the test itself.
    blocks = re.findall(r'(?m)^failures:\s*\n((?:[ \t]+\S+\s*\n)+)', text)
    names = set(FAILED_NAME.findall(blocks[-1])) if blocks else set()
    assert len(names) == failed, (names, failed)
    assert (summaries[0].group(1) == 'FAILED') == bool(failed)
    return {'count':expected_count,'passed':passed,'failed':failed,'failures':sorted(names)}

def check(out):
    out = Path(out)
    result = {'release_qualified':False}
    for arm,n in [('control',42),('candidate',45)]:
        parsed = parse((out/f'{arm}.tests.log').read_text(), n)
        parsed['rc'] = int((out/f'{arm}.tests.rc').read_text())
        assert set(parsed['failures']) == EXPECTED, (arm,parsed)
        assert parsed['rc'] == 101, (arm,parsed['rc'])
        assert parsed['passed'] == n - len(EXPECTED)
        result[arm] = parsed
    result['no_new_test_failures'] = True
    (out/'qualification.json').write_text(json.dumps(result,indent=2))
    print('V88_NO_NEW_TEST_FAILURES=PASS')
    print('V88_RELEASE_QUALIFICATION=BLOCKED_KNOWN_FIXTURES')

if __name__ == '__main__':
    check(sys.argv[1])
