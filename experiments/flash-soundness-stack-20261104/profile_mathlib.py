"""Matched full-Mathlib replay of published Flash and six-guard candidate.

This is not an Arena submission or a proof of complete soundness. It records
exact input/binary hashes, kernel verdict, wall time and peak RSS, including
failures, timeouts and disagreement. A/B/B/A reduces order confounding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def run(binary, config, inp, outdir, arm, index, seconds):
    stem = outdir / f"{index:02d}-{arm}"
    stdout = stem.with_suffix(".stdout")
    stderr = stem.with_suffix(".stderr")
    metrics = stem.with_suffix(".time")
    command = ['/usr/bin/time', '-f',
               'wall_seconds=%e\nuser_seconds=%U\nsys_seconds=%S\npeak_rss_kb=%M',
               '-o', str(metrics), str(binary), str(config)]
    result = {'arm': arm, 'ordinal': index, 'binary_sha256': digest(binary)}
    start = time.monotonic()
    try:
        with inp.open('rb') as source, stdout.open('wb') as so, stderr.open('wb') as se:
            proc = subprocess.run(command, stdin=source, stdout=so,
                                  stderr=se, timeout=seconds, check=False)
        result['returncode'] = proc.returncode
    except subprocess.TimeoutExpired:
        result['returncode'] = 'TIMEOUT'
    result['elapsed_monotonic_seconds'] = round(time.monotonic() - start, 3)
    result['stdout_sha256'] = digest(stdout) if stdout.exists() else None
    result['stderr_sha256'] = digest(stderr) if stderr.exists() else None
    result['stderr_tail'] = stderr.read_bytes()[-500:].decode(errors='replace') if stderr.exists() else None
    if metrics.exists():
        for line in metrics.read_text(errors='replace').splitlines():
            if '=' in line:
                key, val = line.split('=', 1)
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', required=True, type=Path)
    ap.add_argument('--after', required=True, type=Path)
    ap.add_argument('--config', required=True, type=Path)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--outdir', required=True, type=Path)
    ap.add_argument('--seconds', type=int, default=900)
    ap.add_argument('--expected-input-sha256', required=True)
    a = ap.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)
    input_sha = digest(a.input)
    if input_sha != a.expected_input_sha256:
        raise SystemExit(f'input SHA mismatch: {input_sha}')
    report = {'status': 'INCOMPLETE', 'input_sha256': input_sha,
              'input_bytes': a.input.stat().st_size,
              'config_sha256': digest(a.config),
              'published_binary_sha256': digest(a.before),
              'candidate_binary_sha256': digest(a.after),
              'order': ['before', 'after', 'after', 'before'],
              'method': 'sequential A/B/B/A same runner, exact input and config; wall/RSS not arena-calibrated',
              'runs': []}
    path = a.outdir / 'mathlib-report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    for index, arm in enumerate(report['order']):
        binary = a.before if arm == 'before' else a.after
        print('MATHLIB_BEGIN', json.dumps({'index': index, 'arm': arm}), flush=True)
        result = run(binary, a.config, a.input, a.outdir, arm, index, a.seconds)
        report['runs'].append(result)
        path.write_text(json.dumps(report, indent=2) + '\n')
        print('MATHLIB_RUN', json.dumps(result), flush=True)
        if result['returncode'] != 0:
            print('MATHLIB_STOP', json.dumps({'cause': 'non-ACCEPT, timeout or resource failure',
                                             'index': index, 'arm': arm}), flush=True)
            break
    both_arms = {arm: [r for r in report['runs'] if r['arm'] == arm]
                 for arm in ('before', 'after')}
    valid = len(report['runs']) == 4 and all(r['returncode'] == 0 for r in report['runs'])
    if valid:
        for arm, rs in both_arms.items():
            report[f'{arm}_median_wall_seconds'] = statistics.median(r['wall_seconds'] for r in rs)
            report[f'{arm}_max_peak_rss_kb'] = max(r['peak_rss_kb'] for r in rs)
        report['candidate_vs_published_wall_ratio'] = (
            report['after_median_wall_seconds'] / report['before_median_wall_seconds'])
        report['status'] = 'BOUNDED_MATCHED_MATHLIB_ACCEPTANCE'
    else:
        report['status'] = 'UNKNOWN_OR_REJECTED_MATCHED_MATHLIB'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('MATHLIB_STACK_SUMMARY', json.dumps({
        k: v for k, v in report.items() if k != 'runs'}), flush=True)
    if not valid:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
