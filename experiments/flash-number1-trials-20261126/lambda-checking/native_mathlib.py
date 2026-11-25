"""Matched full-input diagnostic, with explicit unknown resource stops.

No process status is converted into a semantic verdict. CPU time is a diagnostic,
never an Arena instruction score. Source and executable identities are checked by
the workflow before this script runs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def tree_rss_kb(pid):
    pending, seen, total = [pid], set(), 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f'/proc/{current}/status').read_text()
            m = re.search(r'^VmRSS:\s+(\d+) kB$', status, re.M)
            if m:
                total += int(m.group(1))
            pending.extend(int(p) for p in Path(
                f'/proc/{current}/task/{current}/children').read_text().split())
        except (OSError, ValueError):
            pass
    return total


def run_bounded(cmd, fixture, stdout, stderr, seconds, rss_limit):
    start, peak, stop = time.monotonic(), 0, None
    with fixture.open('rb') as inp, stdout.open('wb') as out, stderr.open('wb') as err:
        proc = subprocess.Popen(cmd, stdin=inp, stdout=out, stderr=err, start_new_session=True)
        while proc.poll() is None:
            peak = max(peak, tree_rss_kb(proc.pid))
            if peak > rss_limit:
                stop = 'UNKNOWN_RSS_DIAGNOSTIC_BUDGET'
            elif time.monotonic() - start > seconds:
                stop = 'UNKNOWN_TIME_DIAGNOSTIC_BUDGET'
            if stop:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.2)
        raw = proc.wait()
    return {'raw_exit': raw, 'diagnostic_stop': stop,
            'elapsed_s': time.monotonic() - start, 'monitored_tree_peak_rss_kb': peak}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--binaries', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--seconds', type=int, default=360)
    p.add_argument('--rss-kb', type=int, default=11534336)
    p.add_argument('--rounds', type=int, default=2)
    p.add_argument('--time', type=Path, default=Path('/usr/bin/time'))
    p.add_argument('--profile', action='store_true')
    a = p.parse_args()
    assert a.seconds > 0 and a.rss_kb > 0 and a.rounds > 0
    a.out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(Path(__file__).with_name('protocol.json').read_text())
    manifest = json.loads((Path(__file__).parent.parent / 'official-mathlib-input.json').read_text())
    actual = {'size': a.fixture.stat().st_size, 'sha256': digest(a.fixture)}
    expected = {k: manifest['test'][k] for k in actual}
    save(a.out / 'input-identity.json', {'actual': actual, 'expected': expected,
                                       'authority': manifest['authority']})
    assert actual == expected, 'Full Mathlib input differs'
    arms = [r['name'] for r in protocol['arms']]
    bins = {arm: (a.binaries / (arm + '.bin')).resolve() for arm in arms}
    hashes = {arm: digest(path) for arm, path in bins.items()}
    save(a.out / 'binary-identities.json', hashes)
    assert len(set(hashes.values())) == len(arms), 'Shared executable invalidates comparison'
    cfg = (a.out / 'config.json').resolve()
    config = {'use_stdin': True, 'num_threads': 2, 'parse_only': False,
              'nat_extension': True, 'string_extension': True,
              'unsafe_permit_all_axioms': True, 'unpermitted_axiom_hard_error': False,
              'print_success_message': True, 'print_axioms': False}
    save(cfg, config)
    probe = subprocess.run(['perf', 'stat', '-x,', '-e', 'instructions:u', '--', 'true'],
                           capture_output=True, timeout=15) if shutil.which('perf') else None
    pmu = probe is not None and probe.returncode == 0 and re.search(
        rb'(?m)^\d+,,instructions:u', probe.stderr) is not None
    save(a.out / 'pmu-probe.json', {'usable': pmu,
        'raw_exit': None if probe is None else probe.returncode,
        'stderr': 'perf unavailable' if probe is None else probe.stderr.decode(errors='replace')})
    rows, unavailable = [], set()
    for round_no in range(a.rounds):
        for arm in arms if round_no % 2 == 0 else reversed(arms):
            if arm in unavailable:
                continue
            tag = f'{arm}-{round_no}'
            timing, perf = a.out / (tag + '.time'), a.out / (tag + '.perf')
            stdout, stderr = a.out / (tag + '.stdout'), a.out / (tag + '.stderr')
            cmd = [str(a.time), '-f', '%e\t%U\t%S\t%M', '-o', str(timing)]
            if pmu:
                cmd += ['perf', 'stat', '-x,', '-e', 'instructions:u', '-o', str(perf), '--']
            cmd += [str(bins[arm]), str(cfg)]
            row = run_bounded(cmd, a.fixture, stdout, stderr, a.seconds, a.rss_kb)
            row.update({'arm': arm, 'round': round_no, 'binary_sha256': hashes[arm],
                        'input_sha256': actual['sha256'], 'expected_exit': 0,
                        'success_message': re.fullmatch(rb'Checked \d+ declarations with no errors\s*',
                                                       stdout.read_bytes()) is not None,
                        'stderr_tail': stderr.read_bytes()[-1600:].decode(errors='replace')})
            lines = timing.read_text().strip().splitlines() if timing.exists() else []
            fields = lines[-1].split('\t') if lines else []
            if len(fields) == 4:
                row.update({'wall_s': float(fields[0]), 'user_s': float(fields[1]),
                            'system_s': float(fields[2]), 'max_rss_kb': int(fields[3])})
                row['cpu_s'] = row['user_s'] + row['system_s']
            if perf.exists():
                m = re.search(r'(?m)^(\d+),,instructions:u(?:,|$)', perf.read_text())
                if m:
                    row['instructions_u'] = int(m.group(1))
            rows.append(row)
            save(a.out / 'rows.json', rows)
            print(json.dumps(row), flush=True)
            if row['raw_exit'] != 0 or not row['success_message'] or row['diagnostic_stop']:
                unavailable.add(arm)
                if arm == 'baseline':
                    break
        if 'baseline' in unavailable:
            break
    summary = {'status': 'BOUNDED_FULL_MATHLIB_DIAGNOSTIC', 'unavailable_arms': sorted(unavailable),
               'rows': len(rows), 'hardware_counter_usable': pmu,
               'boundary': 'Not ten-large-case qualification or an official Arena ranking.',
               'candidate_over_baseline_cpu': {}}
    if 'baseline' not in unavailable:
        baseline = [r['cpu_s'] for r in rows if r['arm'] == 'baseline' and 'cpu_s' in r]
        if len(baseline) == a.rounds:
            for arm in arms[1:]:
                values = [r['cpu_s'] for r in rows if r['arm'] == arm and 'cpu_s' in r]
                if arm not in unavailable and len(values) == a.rounds:
                    summary['candidate_over_baseline_cpu'][arm] = statistics.geometric_mean(values) / statistics.geometric_mean(baseline)
    save(a.out / 'summary.json', summary)
    print('SUMMARY', json.dumps(summary), flush=True)
    eligible = [(v, k) for k, v in summary['candidate_over_baseline_cpu'].items() if v <= 0.95]
    profile_decision = {'gate': 'both complete native rounds; CPU ratio <= 0.95',
                        'eligible': eligible, 'selected': None, 'status': 'NOT_RUN'}
    save(a.out / 'profile-decision.json', profile_decision)
    if a.profile and eligible:
        ratio, arm = min(eligible)
        config['num_threads'] = 1
        save(a.out / 'profile-config.json', config)
        profile = a.out / (arm + '.callgrind')
        cmd = ['valgrind', '--tool=callgrind', '--callgrind-out-file=' + str(profile),
               str(bins[arm]), str((a.out / 'profile-config.json').resolve())]
        row = run_bounded(cmd, a.fixture, a.out / 'profile.stdout', a.out / 'profile.stderr', 5400, 13631488)
        row.update({'arm': arm, 'native_cpu_ratio': ratio, 'binary_sha256': hashes[arm],
                    'input_sha256': actual['sha256'], 'historical_baseline_guest_Ir': 1022208383890,
                    'historical_baseline_run': 45557672555,
                    'boundary': 'Historical same-source/compiler/flags/input baseline, not simultaneous or an official Arena score.'})
        if row['raw_exit'] == 0 and row['diagnostic_stop'] is None and profile.exists():
            m = re.findall(r'^summary:\s*(\d+)', profile.read_text(), re.M)
            if m:
                row['guest_Ir'] = int(m[-1])
                row['historical_ratio'] = row['guest_Ir'] / row['historical_baseline_guest_Ir']
                subprocess.run(['callgrind_annotate', '--inclusive=no', '--threshold=99', str(profile)],
                               stdout=(a.out / 'profile-exclusive.txt').open('wb'), check=True)
        profile_decision.update({'selected': arm, 'status': 'MEASURED' if 'guest_Ir' in row else 'UNKNOWN', 'result': row})
        save(a.out / 'profile-decision.json', profile_decision)
        print('PROFILE', json.dumps(profile_decision), flush=True)
    if unavailable:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
