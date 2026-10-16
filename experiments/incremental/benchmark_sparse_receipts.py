#!/usr/bin/env python3
"""Separate storage experiment. Capsules never constitute acceptance evidence.

Both writers mint the original full accepted HMAC/envelope/content address.
Sparse adds a complete patch scan and a signed storage representation. Its
reader authenticates the baseline, reconstructs the original complete record,
then calls the unchanged engine acceptance authenticator. No kernel is run.
"""
import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path
import random
import resource
import statistics
import subprocess
import sys
import time

import engine
from producer_delta import authenticate, seal

SCHEMA = 'mathgraph.sparse-accepted-record-representation.v1'
SCOPE = 'storage_only_not_acceptance'
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    return json.loads(raw, object_pairs_hook=engine.strict_object)


def mint_original(payload, key):
    raw = engine.encoded(seal(payload, key))
    return raw, sha(raw)


def representation(base, base_id, current, signature, original_id):
    if current.get('previous_evidence') != base_id:
        raise ValueError('different previous baseline')
    if current['provenance'] != base['provenance']:
        raise ValueError('different verification policy')
    before, after = base['index'], current['index']
    for field in ('meta', 'count', 'builtins', 'complex', 'schedule'):
        if before[field] != after[field]:
            raise ValueError('unsupported index global transition: ' + field)
    if len(before['declarations']) != len(after['declarations']):
        raise ValueError('different declaration count')
    patches = []
    for position, (old, new) in enumerate(zip(before['declarations'], after['declarations'])):
        if old['key'] != new['key'] or old['index'] != position or new['index'] != position:
            raise ValueError('different declaration schedule')
        if old != new:
            patches.append(dict(position=position, baseline_key=old['key'],
                baseline_own=old['own'], baseline_closure=old['closure'], declaration=new))
    return dict(schema=SCHEMA, scope=SCOPE, base_evidence_id=base_id,
        accepted_evidence_id=original_id, accepted_hmac_sha256=signature,
        accepted_header={k: v for k, v in current.items() if k != 'index'},
        index_header={k: v for k, v in after.items() if k != 'declarations'}, replacements=patches)


def expand(raw, capsule_id, baseline_reader, key):
    if sha(raw) != capsule_id:
        raise ValueError('storage capsule content address mismatch')
    capsule = authenticate(decode(raw), key, SCHEMA)
    expected = {'schema', 'scope', 'base_evidence_id', 'accepted_evidence_id',
                'accepted_hmac_sha256', 'accepted_header', 'index_header', 'replacements'}
    if set(capsule) != expected or capsule['scope'] != SCOPE:
        raise ValueError('invalid storage capsule fields/scope')
    base_id = capsule['base_evidence_id']
    if type(base_id) is not str or len(base_id) != 64 or any(c not in '0123456789abcdef' for c in base_id):
        raise ValueError('invalid baseline identifier')
    base = engine.authenticate_record(baseline_reader(base_id), base_id, key)
    header, index_header = capsule['accepted_header'], capsule['index_header']
    if ('index' in header or header.get('previous_evidence') != base_id or
            header.get('provenance') != base['provenance']):
        raise ValueError('different previous baseline or verification policy')
    expected_header = {k: v for k, v in base['index'].items() if k != 'declarations'}
    if index_header != expected_header:
        raise ValueError('unsupported index global transition')
    declarations = list(base['index']['declarations'])
    last = -1
    for patch in capsule['replacements']:
        if set(patch) != {'position', 'baseline_key', 'baseline_own', 'baseline_closure', 'declaration'}:
            raise ValueError('invalid storage patch fields')
        position = patch['position']
        if type(position) is not int or not last < position < len(declarations):
            raise ValueError('patch positions must be unique sorted integers in range')
        last = position
        old, new = declarations[position], patch['declaration']
        if (patch['baseline_key'] != old['key'] or patch['baseline_own'] != old['own'] or
                patch['baseline_closure'] != old['closure'] or new['key'] != old['key'] or
                type(new['index']) is not int or new['index'] != position):
            raise ValueError('baseline patch guard mismatch')
        declarations[position] = new
    index = dict(index_header, declarations=declarations)
    payload = dict(header, index=index)
    original = engine.encoded(dict(payload=payload, hmac_sha256=capsule['accepted_hmac_sha256']))
    # Only the original acceptance schema/status/HMAC/content address authorizes
    # this reconstructed record. The storage-domain signature is insufficient.
    return engine.authenticate_record(original, capsule['accepted_evidence_id'], key)


def cpu():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def memory():
    values = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            name, number, unit = line.split()
            values[name[:-1] + '_' + unit] = int(number)
    return values


def measured(call):
    start, started_cpu = time.perf_counter(), cpu()
    result = call()
    elapsed, used = time.perf_counter() - start, cpu() - started_cpu
    return result, dict(wall_seconds=elapsed, cpu_seconds=used, postphase_memory=memory())


def write_report(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def compare(samples, field):
    pairs = [(s['full'][field]['wall_seconds'], s['sparse'][field]['wall_seconds']) for s in samples]
    full = statistics.median(x for x, _ in pairs)
    sparse = statistics.median(y for _, y in pairs)
    rng = random.Random(20261016)
    ratios = []
    for _ in range(10000):
        rows = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        ratios.append(statistics.median(y for _, y in rows) / statistics.median(x for x, _ in rows))
    ratios.sort()
    lo, hi = ratios[249], ratios[9749]
    wins = sum(y < x for x, y in pairs)
    passed = len(pairs) >= 5 and sparse < full and wins >= 4 and hi < 1
    return dict(full_median_wall_seconds=full, sparse_median_wall_seconds=sparse,
        sparse_over_full_median_ratio=sparse/full, paired_wins=wins, paired_count=len(pairs),
        bootstrap_ratio_interval_95=[lo, hi], bootstrap_repetitions=10000, bootstrap_seed=20261016,
        full_median_cpu_seconds=statistics.median(s['full'][field]['cpu_seconds'] for s in samples),
        sparse_median_cpu_seconds=statistics.median(s['sparse'][field]['cpu_seconds'] for s in samples),
        status='SPEEDUP' if passed else 'NO_SPEEDUP', passed=passed)


def input_cases(summary_path, key, profile):
    summary_path = Path(summary_path).resolve()
    raw = summary_path.read_bytes()
    summary = decode(raw)
    expected_profile = {'original':'original-qualified-3436', 'expanded':'std-hashmap-expanded-v1'}[profile]
    if (summary.get('schema') != 'mathgraph.authenticated-producer-delta-qualification.v1' or
            summary.get('profile') != expected_profile or
            summary.get('run_completed') is not True or summary.get('correctness_passed') is not True or
            summary.get('qualification_status') != 'PASS' or not summary.get('gates') or
            not all(g.get('passed') is True for g in summary['gates'])):
        raise ValueError('original kernel qualification is not complete/pass')
    cases = []
    for variant in ('early-definition', 'unrelated-definition'):
        matches = [s for s in summary['samples'] if s['variant'] == variant and not s['cold_replay']]
        if len(matches) < 5:
            raise ValueError('original kernel qualification lacks five pairs')
        sample = min(matches, key=lambda s: s.get('repetition', 0))
        directory = Path(sample['result_path']).parent
        base_id, accepted_id = sample['baseline_result']['evidence_id'], sample['evidence_id']
        base_path = directory / 'session/baseline-cache/records' / (base_id + '.json')
        accepted_path = directory / 'session/cache/records' / (accepted_id + '.json')
        base_raw, accepted_raw = base_path.read_bytes(), accepted_path.read_bytes()
        base = engine.authenticate_record(base_raw, base_id, key)
        accepted = engine.authenticate_record(accepted_raw, accepted_id, key)
        if (accepted['previous_evidence'] != base_id or
                accepted['index']['count'] != sample['partition_audit']['actual_kernel_total']):
            raise ValueError('authenticated original record/partition mismatch')
        original, original_id = mint_original(accepted, key)
        if original != accepted_raw or original_id != accepted_id:
            raise ValueError('original receipt is not canonical existing issuer representation')
        cases.append(dict(profile=profile, variant=variant, base=base, current=accepted,
            base_id=base_id, original_id=accepted_id, base_path=base_path,
            source=dict(profile=profile, variant=variant, summary_path=str(summary_path), summary_sha256=sha(raw),
                kernel_source=summary['source_git_commit'], base_path=str(base_path),
                base_sha256=sha(base_raw), accepted_path=str(accepted_path), accepted_sha256=sha(accepted_raw),
                total=accepted['index']['count'], original_receipt_bytes=len(accepted_raw))))
    return cases


def controls(case, capsule_raw, capsule_id, key, directory):
    base_raw = case['base_path'].read_bytes()
    capsule = decode(capsule_raw)['payload']
    checks = []
    def refusal(name, raw, ident, baseline, used_key, expected):
        try:
            expand(raw, ident, lambda _: baseline, used_key)
        except ValueError as error:
            checks.append(dict(name=name, passed=expected in str(error), expected=expected, observed=str(error)))
        else:
            checks.append(dict(name=name, passed=False, expected=expected, observed='ACCEPTED'))
    forged = decode(capsule_raw); forged['hmac_sha256'] = '0' * 64
    raw = engine.encoded(forged)
    refusal('forged_capsule_hmac', raw, sha(raw), base_raw, key, 'issuer authentication failed')
    refusal('corrupt_capsule', capsule_raw + b' ', capsule_id, base_raw, key, 'storage capsule content address mismatch')
    refusal('corrupt_base', capsule_raw, capsule_id, base_raw + b' ', key, 'evidence content address mismatch')
    refusal('wrong_key', capsule_raw, capsule_id, base_raw, bytes(x ^ 255 for x in key), 'issuer authentication failed')
    for name in ('bad_patch', 'bad_patch_new_content_id', 'version', 'duplicate_patch', 'baseline_guard'):
        modified = copy.deepcopy(capsule)
        if name in ('bad_patch', 'bad_patch_new_content_id'):
            modified['replacements'][0]['declaration']['own'] = 'forged-original-acceptance'
            reason = 'evidence content address mismatch'
            if name == 'bad_patch_new_content_id':
                changed = copy.deepcopy(case['current'])
                patch = modified['replacements'][0]
                changed['index']['declarations'][patch['position']] = patch['declaration']
                altered = engine.encoded(dict(payload=changed, hmac_sha256=modified['accepted_hmac_sha256']))
                modified['accepted_evidence_id'] = sha(altered)
                reason = 'evidence issuer authentication failed'
        elif name == 'version':
            modified['schema'] += '.wrong'; reason = 'wrong authority domain'
        elif name == 'duplicate_patch':
            modified['replacements'] *= 2; reason = 'patch positions'
        else:
            modified['replacements'][0]['baseline_own'] = 'foreign'; reason = 'baseline patch guard'
        raw = engine.encoded(seal(modified, key))
        refusal('validly_resigned_' + name, raw, sha(raw), base_raw, key, reason)
    # Actual new interpreter: no resident authenticated baseline/index state.
    for arm in ('full', 'sparse'):
        spec = directory / (arm + '-cold-spec.json')
        write_report(spec, dict(arm=arm, record_path=str(directory / (arm + '.json')),
            record_id=case['original_id'] if arm == 'full' else capsule_id,
            base_path=str(case['base_path']), key_path=str(case['key_path']), expected_id=case['original_id']))
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--reader', str(spec)],
                                 capture_output=True, timeout=120)
        write_report(directory / (arm + '-cold-process.json'), dict(command=[sys.executable, str(Path(__file__).resolve()), '--reader', str(spec)],
            returncode=process.returncode, stdout=process.stdout.decode(errors='replace'), stderr=process.stderr.decode(errors='replace')))
        checks.append(dict(name='fresh_interpreter_' + arm, passed=process.returncode == 0 and
            decode(process.stdout).get('accepted_evidence_id') == case['original_id'] if process.returncode == 0 else False))
    return checks


def reader(spec_path):
    spec = decode(Path(spec_path).read_bytes())
    key = Path(spec['key_path']).read_bytes()
    raw = Path(spec['record_path']).read_bytes()
    payload = (engine.authenticate_record(raw, spec['record_id'], key) if spec['arm'] == 'full' else
               expand(raw, spec['record_id'], lambda _: Path(spec['base_path']).read_bytes(), key))
    original, ident = mint_original(payload, key)
    if ident != spec['expected_id']:
        raise ValueError('fresh interpreter reconstructed another accepted record')
    print(json.dumps(dict(status='AUTHENTICATED_EXISTING_RECORD', accepted_evidence_id=ident,
                          total=payload['index']['count'], scope=SCOPE)))


def validate_parity_gate(gate, allow_incomplete):
    if (gate.get('schema') != 'mathgraph.retained-index-qualification.v1' or
            gate.get('run_completed') is not True or not gate.get('gates') or
            not all(g.get('passed') is True for g in gate['gates']) or
            (not allow_incomplete and (gate.get('correctness_passed') is not True or
                                      gate.get('qualification_status') != 'PASS'))):
        raise ValueError('retained transition parity gate is not complete/pass')


def run(args):
    args.out = Path(args.out).resolve()
    keys = {'original': Path(args.authority_key).resolve(),
            'expanded': Path(args.expanded_authority_key or args.authority_key).resolve()}
    if any(args.out == p or args.out in p.parents for p in keys.values()):
        raise ValueError('issuer keys must stay outside output')
    if args.repetitions < 5:
        raise ValueError('at least five paired repetitions required')
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError('fresh output directory required')
    gate_raw = Path(args.retained_summary).read_bytes(); gate = decode(gate_raw)
    validate_parity_gate(gate, args.allow_incomplete_parity_smoke)
    args.out.mkdir(parents=True)
    report = dict(schema='mathgraph.sparse-storage-benchmark.v1', run_completed=False,
        correctness_passed=False, qualification_status='IN_PROGRESS', scope=SCOPE,
        source_sha=subprocess.check_output(['git','rev-parse','HEAD'], cwd=HERE, text=True).strip(),
        helper_sha256=sha(Path(__file__).read_bytes()), engine_sha256=sha((HERE/'engine.py').read_bytes()),
        parity_gate=dict(path=str(Path(args.retained_summary).resolve()), sha256=sha(gate_raw),
            qualification_status=gate.get('qualification_status'), incomplete_smoke_allowed=args.allow_incomplete_parity_smoke),
        host=dict(uname=list(platform.uname())), repetitions=args.repetitions, samples=[], controls={}, inputs=[],
        measurement_policy=dict(writer='Both arms canonicalize/sign/hash the identical existing accepted full payload; sparse additionally scans all declarations, signs its capsule and fsyncs it',
            reader='Fresh reads and baseline authentication every sparse call, full reconstruction, canonical original envelope/content-id and existing whole accepted HMAC reauthentication; no trusted baseline cache',
            order='alternating full/sparse and reverse by repetition; writer then reader per arm',
            costs='input fixture authentication/decompression and equality oracles outside timings; both complete writer and reader paths timed',
            cpu='current process user+system CPU; no live kernel/producer worker',
            memory='postphase process RSS and cumulative startup-inclusive VmHWM; no aggregate/phase-peak/savings claim',
            limits='storage representation only, no inference, new acceptance, producer-pipeline integration, end-to-end speedup or change-proportional cold cost'))
    write_report(args.out/'summary.json', report)
    for profile, source in (('original', args.summary), ('expanded', args.expanded_summary)):
        key = keys[profile].read_bytes()
        if len(key) != 32:
            raise ValueError('issuer key must contain32bytes')
        for case in input_cases(source, key, profile):
            case['key_path'] = keys[profile]
            name = profile + ':' + case['variant']; report['inputs'].append(case['source'])
            directory = args.out/profile/case['variant']; directory.mkdir(parents=True)
            samples = []
            for repetition in range(args.repetitions):
                sample = dict(profile=profile, variant=case['variant'], repetition=repetition,
                              order=['full','sparse'] if repetition%2 == 0 else ['sparse','full'])
                for arm in sample['order']:
                    path = directory / (arm + '.json')
                    # Every write is a genuinely new immutable write+file fsync.
                    if path.exists(): path.unlink()
                    def writer():
                        original_signed = seal(case['current'], key)
                        original = engine.encoded(original_signed)
                        original_id = sha(original)
                        if arm == 'full':
                            raw, ident, patches = original, original_id, None
                        else:
                            cap = representation(case['base'], case['base_id'], case['current'],
                                                 original_signed['hmac_sha256'], original_id)
                            raw = engine.encoded(seal(cap, key)); ident, patches = sha(raw), len(cap['replacements'])
                        engine.immutable_write(path, raw)
                        return ident, len(raw), patches
                    (ident, size, patches), write_timing = measured(writer)
                    def read():
                        raw = path.read_bytes()
                        return engine.authenticate_record(raw, ident, key) if arm == 'full' else expand(raw, ident, lambda _: case['base_path'].read_bytes(), key)
                    payload, read_timing = measured(read)
                    if payload != case['current']:
                        raise ValueError('reconstructed existing accepted payload differs')
                    sample[arm] = dict(write=write_timing, read=read_timing, bytes=size,
                                       record_id=ident, patches=patches, includes_original_acceptance_mint=True)
                samples.append(sample); report['samples'].append(sample)
            raw = (directory/'sparse.json').read_bytes()
            report['controls'][name] = controls(case, raw, sha(raw), key, directory)
            report.setdefault('economics', {})[name] = {phase: compare(samples, phase) for phase in ('write','read')}
            write_report(args.out/'summary.json', report)
            print(json.dumps(dict(case=name, correctness=all(c['passed'] for c in report['controls'][name]),
                economics={k:v['status'] for k,v in report['economics'][name].items()})), flush=True)
    expected = {'original:early-definition','original:unrelated-definition','expanded:early-definition','expanded:unrelated-definition'}
    okay = set(report['controls']) == expected and len(report['samples']) == 4*args.repetitions and all(
        c['passed'] for rows in report['controls'].values() for c in rows)
    report.update(run_completed=True, correctness_passed=okay, qualification_status='PASS' if okay else 'FAIL')
    write_report(args.out/'summary.json', report)
    return 0 if okay else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reader')
    for arg in ('summary','expanded-summary','retained-summary','authority-key','expanded-authority-key','out'):
        parser.add_argument('--'+arg)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--allow-incomplete-parity-smoke', action='store_true')
    args = parser.parse_args()
    if args.reader:
        reader(args.reader); return 0
    if not all(getattr(args,k) for k in ('summary','expanded_summary','retained_summary','authority_key','out')):
        parser.error('both original qualification summaries, retained parity summary, issuer key and output are required')
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
