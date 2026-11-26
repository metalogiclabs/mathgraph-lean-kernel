"""Keep source/input acceptance, resource and software-cost gates explicit."""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mode', choices=['native', 'instructions'], required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
checks = {}
if a.mode == 'native':
    portable = json.loads((a.out / 'portable/summary.json').read_text())
    rows = json.loads((a.out / 'native/rows.json').read_text())
    checks['all_230_portable_correct'] = portable['attempted'] == portable['correct'] == 230
    checks['four_complete_accepts'] = len(rows) == 4 and all(
        r['observed'] == 0 and r['declarations'] == 739167 for r in rows)
    peaks = {arm: max(r['max_rss_kb'] for r in rows if r['arm'] == arm)
             for arm in ['baseline', 'strict']}
    limit = max(peaks['baseline'] * 1.10, peaks['baseline'] + 256 * 1024)
    checks['peak_memory_within_declared_limit'] = peaks['strict'] <= limit
    details = {'peak_rss_kb': peaks, 'candidate_peak_limit_kb': limit}
else:
    summary = json.loads((a.out / 'instructions/summary.json').read_text())
    rows = json.loads((a.out / 'instructions/rows.json').read_text())
    checks['four_complete_accepts'] = len(rows) == 4 and all(
        r['raw_exit'] == 0 and r['complete_count'] for r in rows)
    ratios = [next(r['dynamic_instructions'] for r in rows
                   if r['round'] == i and r['arm'] == 'strict') /
              next(r['dynamic_instructions'] for r in rows
                   if r['round'] == i and r['arm'] == 'baseline') for i in range(2)]
    checks['each_pair_saves_one_percent'] = all(r <= .99 for r in ratios)
    checks['aggregate_saves_one_percent'] = summary['strict_to_baseline_ratio'] <= .99
    details = {'paired_ratios': ratios, 'aggregate_ratio': summary['strict_to_baseline_ratio']}
result = {'mode': a.mode, 'passed': all(checks.values()), 'checks': checks,
          'details': details, 'boundary': 'Exact complete-input experiment; not an Arena score or a release qualification of the ten other large inputs.'}
(a.out / 'gate.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
if not result['passed']:
    raise SystemExit(1)
