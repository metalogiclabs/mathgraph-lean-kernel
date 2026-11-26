"""Reconcile the frozen full-input inlining artifact against its declared gates.

Usage: python3 verify_full_artifact.py ARCHIVE.zip OFFICIAL_INPUTS.json OUTPUT.json
This checks retained evidence; it does not rerun Mathlib or establish an Arena
hardware score. The workflow and source tree are separate evidence authorities.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import zipfile

archive, manifest_path, output = map(Path, sys.argv[1:])
sha = lambda b: hashlib.sha256(b).hexdigest()
archive_sha = sha(archive.read_bytes())
assert archive_sha == '6f55b2f7d754e4310589fe74aed040ae98ba82d39ba395bffd7cb6d439a0821e'
manifest = json.loads(manifest_path.read_text())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    read = z.read
    load = lambda name: json.loads(read(name))
    identity = load('comparison/identity.json')
    assert identity['base_commit'] == 'bc704eebed4e009bc66af1a849f18315c11f1926'
    assert identity['baseline_source_tree'] == '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
    assert identity['candidate_source_tree'] == 'de6696fcecbe99e6fcab5bb68c5974e1e9a04e49'
    assert read('candidate-source-tree.txt').decode().strip() == identity['candidate_source_tree']
    assert read('harness-commit.txt').decode().strip() == 'eb070281e4a06e2d729d7d5cabd2185ec7ea6c37'
    assert identity['native_check_workers'] == 2 and identity['count_check_workers'] == 1
    mathlib = next(t for t in manifest['tests'] if t['name'] == 'mathlib')
    assert identity['input_sha256'] == mathlib['sha256'] == 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
    assert identity['input_bytes'] == mathlib['size'] == 6326141213
    for arm, expected in [
        ('baseline', '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'),
        ('candidate', 'a76e2bbfe07ce80b204937548b7a00524bee1bff113fe19c9e1244ed93443f46'),
    ]:
        assert sha(read(f'builds/{arm}.bin')) == identity['binary_sha256'][arm] == expected
        assert read(f'{arm}-build-flags.txt').decode().strip() == '-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'
    assert sha(read('profile.so')) == identity['client_sha256']
    # sdk-identity.json records the SDK preparer's original client, not profile.so.
    assert load('sdk-identity.json')['archive_sha256'] == '3958421d74964ea2a30b43752560ae584d854ceb6209946dd2d9e173352d7a2c'
    changes = [line for line in read('candidate.patch').decode().splitlines()
               if line[:1] in ('+', '-') and not line.startswith(('+++', '---'))]
    assert changes == ['+    #[inline(always)]']

    expected_portable = {t['name']: t for t in manifest['tests']
                         if t['outcome'] in ('accept', 'reject') and t['size'] <= 10 * 1024**2}
    portable = load('portable/rows.json')
    assert len(portable) == len(expected_portable) == 230
    assert len({r['name'] for r in portable}) == 230
    assert {r['name'] for r in portable} == set(expected_portable)
    assert load('portable/identity.json')['binary_sha256'] == identity['binary_sha256']['candidate']
    for row in portable:
        case = expected_portable[row['name']]
        assert row['sha256'] == case['sha256']
        assert row['expected'] == row['observed'] == (0 if case['outcome'] == 'accept' else 1)
        tag = row['name'].replace('/', '_')
        read(f'portable/{tag}.stdout')
        read(f'portable/{tag}.stderr')
    controls = load('source-controls/rows.json')
    assert len(controls) == len({r['name'] for r in controls}) == 16
    for row in controls:
        assert row['expected'] == row['observed']
        assert sha(read(f"source-controls/{row['name']}.ndjson")) == row['sha256']
    log = read('source-tests.log').decode()
    assert 'test result: ok. 39 passed; 0 failed' in log
    assert 'test result: ok. 2 passed; 0 failed' in log

    def block_sum(name):
        total = 0
        for line in read(name).decode().splitlines():
            kind, address, size, executions = line.split('\t')
            assert kind in ('M', 'L') and int(address, 16) >= 0
            total += int(size) * int(executions)
        return total

    for row in load('comparison/calibration.json'):
        n = row['iterations']
        assert row['raw_exit'] == 0
        assert row['instructions'] == row['expected'] == row['sum'] == 3 * n + 5
        assert block_sum(f'comparison/calibration-{n}.tsv') == 3 * n + 5
    negative = load('comparison/shared-cache-negative.json')
    assert negative['raw_exit'] == 255 and negative['instructions'] is None
    rows = load('comparison/rows.json')
    assert [(r['mode'], r['arm'], r['round']) for r in rows] == [
        (mode, arm, n) for mode in ('native', 'count') for n, order in enumerate(
            [('baseline', 'candidate'), ('candidate', 'baseline')]) for arm in order]
    for row in rows:
        tag = f"{row['mode']}-{row['arm']}-{row['round']}"
        assert row['raw_exit'] == 0 and row['complete_count'] is True
        out = read(f'comparison/{tag}.stdout').decode()
        assert re.fullmatch(r'checked 739167 declarations in [0-9.]+s\n', out)
        err = read(f'comparison/{tag}.stderr').decode()
        if row['mode'] == 'native':
            assert not err
            user, system, rss, wall = read(f'comparison/{tag}.time').decode().split()
            assert math.isclose(row['cpu_s'], float(user) + float(system))
            assert row['max_rss_kb'] == int(rss) and row['wall_s'] == float(wall)
        else:
            markers = re.findall(r'FLASH_PROFILE instructions=(\d+) threads=(\d+)', err)
            assert markers == [(str(row['instructions']), str(row['threads']))]
            assert row['instructions'] == row['block_sum'] == block_sum(f'comparison/{tag}.tsv')
    counts = {(r['arm'], r['round']): r['instructions'] for r in rows if r['mode'] == 'count'}
    paired = [counts['candidate', n] / counts['baseline', n] for n in (0, 1)]
    cpu = {arm: statistics.median(r['cpu_s'] for r in rows if r['mode'] == 'native' and r['arm'] == arm)
           for arm in ('baseline', 'candidate')}
    rss = {arm: max(r['max_rss_kb'] for r in rows if r['mode'] == 'native' and r['arm'] == arm)
           for arm in ('baseline', 'candidate')}
    summary = load('comparison/summary.json')
    assert summary['instruction_paired_ratios'] == paired
    assert summary['instruction_geometric_ratio'] == math.sqrt(math.prod(paired))
    assert summary['cpu_medians_s'] == cpu and summary['peak_rss_kb'] == rss
    assert summary['cpu_ratio'] == cpu['candidate'] / cpu['baseline']
    assert summary['peak_rss_ratio'] == rss['candidate'] / rss['baseline']
    passed = all(r <= .99 for r in paired) and summary['cpu_ratio'] <= 1.05 and summary['peak_rss_ratio'] <= 1.10
    assert passed and summary['passed'] and summary['state'] == 'CANDIDATE_FULL_MATHLIB_GATE_PASSED'
    report = {
        'state': 'WARRANTED_BOUNDED_FULL_MATHLIB_INSTRUCTION_REDUCTION',
        'run': 45723515088, 'artifact': 15073369717, 'archive_sha256': archive_sha,
        'archive_files': len(z.namelist()), 'identity': identity,
        'portable_correct': 230, 'source_controls_correct': 16,
        'library_tests': 39, 'integration_tests': 2,
        'complete_mathlib_executions': 8, 'declarations_per_execution': 739167,
        'summary': summary,
        'decision': 'Retain as separate CANDIDATE; do not replace the qualified bc704 source in Arena PR398. Count reduction is repeatable, but these native CPU observations do not establish a speedup.',
        'remaining_UNKNOWN': ['other nine large inputs on this variant', 'Arena target-cpu=native hardware event and public score'],
        'historical_unknowns': 'Local SIGKILL observations and invalidated mutable-binary run remain preserved. This isolated CI run resolves only its own stated boundaries.',
        'sdk_note': '32-bit SDK library warnings are retained in raw stderr. The 64-bit counter completed; three exact calibration totals and all additive full block sums match. SDK preparer client identity differs from the actually measured profile.so recorded above.',
    }
output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ('state', 'portable_correct', 'source_controls_correct', 'complete_mathlib_executions', 'summary')}))
