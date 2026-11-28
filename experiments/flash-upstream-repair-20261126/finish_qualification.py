"""Join the remaining exact-source export into the already verified qualification."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile

REPO = 'metalogiclabs/mathgraph-lean-kernel'
JOB = 139547527336
RUN = 45711718821
SOURCE = '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
root = Path('experiments/flash-upstream-repair-20261126')
out = Path(os.environ['RUNNER_TEMP']) / 'final-flash-qualification'
out.mkdir(exist_ok=True)


def api(path, binary=False):
    result = subprocess.run(['gh', 'api', f'repos/{REPO}/' + path],
        capture_output=True, check=True)
    return result.stdout if binary else json.loads(result.stdout)


def verify_export(files, target):
    assert files['source-tree.txt'].decode().strip() == SOURCE
    verdict = json.loads(files['verdict.json'])
    identity = json.loads(files['input.json'])
    assert identity['size'] == target['size'] and identity['sha256'] == target['sha256']
    assert verdict['name'] == target['name'] and verdict['input_sha256'] == target['sha256']
    assert verdict['raw_exit'] == 0 and verdict['checked_declarations'] > 0 and verdict['threads'] == 2
    assert files['binary.txt'].decode().split()[0] == verdict['binary_sha256']
    success = f"checked {verdict['checked_declarations']} declarations"
    assert success in files['stdout.txt'].decode().lower()
    return verdict


capsule = json.loads((root / 'qualification-capsule.json').read_text())
assert capsule['source_tree'] == SOURCE
manifest = {t['name']: t for t in json.loads((root / 'official-inputs.json').read_text())['tests']
    if t['outcome'] in ['accept', 'reject']}
assert len(manifest) == 240
observations = capsule['prescribed_observations']
assert set(manifest) - set(observations) == {'navier-stokes-euler'}
for name, row in observations.items():
    expected = manifest[name]
    assert row['input_sha256'] == expected['sha256']
    assert row['raw_exit'] == (0 if expected['outcome'] == 'accept' else 1)
for record in capsule['raw_text_entries'].values():
    assert hashlib.sha256(record['utf8'].encode()).hexdigest() == record['sha256']

deadline = time.monotonic() + 85 * 60
while True:
    job = api(f'actions/jobs/{JOB}')
    if job['status'] == 'completed':
        (out / 'remaining-job.json').write_text(json.dumps(job, indent=2) + '\n')
        if job['conclusion'] != 'success':
            print('UNKNOWN_REMAINING_EXPORT_OR_CHECK', job['conclusion'], flush=True)
            raise SystemExit(1)
        break
    if time.monotonic() > deadline:
        raise SystemExit('UNKNOWN_REMAINING_JOB_STILL_RUNNING')
    time.sleep(30)

artifacts = api(f'actions/runs/{RUN}/artifacts')['artifacts']
matches = [a for a in artifacts if a['name'] == 'flash-reconciled-large-navier-stokes-euler']
assert len(matches) == 1
artifact = matches[0]
archive = api(f"actions/artifacts/{artifact['id']}/zip", binary=True)
digest = hashlib.sha256(archive).hexdigest()
assert artifact['digest'] == 'sha256:' + digest
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    assert z.testzip() is None
    files = {}
    for name in z.namelist():
        p = Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        if not name.endswith('/'):
            files[name] = z.read(name)
target = manifest['navier-stokes-euler']
verdict = verify_export(files, target)

provenance = {'artifact_id': artifact['id'], 'run_id': RUN,
    'head_sha': artifact['workflow_run']['head_sha'], 'archive_sha256': digest}
prefix = 'ci-large/flash-reconciled-large-navier-stokes-euler/'
for name, value in files.items():
    capsule['raw_text_entries'][prefix + name] = {
        'sha256': hashlib.sha256(value).hexdigest(), 'utf8': value.decode('utf-8')}
observations['navier-stokes-euler'] = {'raw_exit': 0,
    'input_sha256': target['sha256'], 'source': prefix + 'verdict.json', 'archive': provenance}
assert set(observations) == set(manifest)
capsule.update(state='WARRANTED_BOUNDED_ALL_240_AND_COMPLETE_MATHLIB',
    prescribed_confirmed=240, pending_prescribed=[])
capsule['boundary'] = ('All 240 byte-exact prescribed verdicts; two-worker matched native Mathlib '
    'CPU/RSS and separate one-worker software instruction diagnostic. Thirty policy cases, '
    'universal soundness, official hardware scoring and any new rank remain separate boundaries.')
(out / 'qualification-capsule.json').write_text(json.dumps(capsule, indent=2) + '\n')
(out / 'navier-archive.json').write_text(json.dumps(provenance, indent=2) + '\n')
print('ALL_240_PRESCRIBED_PASS', json.dumps(provenance), flush=True)

# Update only our own draft's qualification text, and only at this exact head.
try:
    pr = api('pulls/128')
except subprocess.CalledProcessError:
    print('DRAFT_NOTE_UNAVAILABLE_QUALIFICATION_ALREADY_WRITTEN', flush=True)
    raise SystemExit(0)
if pr['head']['sha'] != os.environ['GITHUB_SHA']:
    print('SKIPPED_DRAFT_UPDATE_HEAD_MOVED', flush=True)
else:
    body = pr['body']
    old = ('239/240 prescribed exact Arena inputs currently confirmed; only the '
        'Navier–Stokes–Euler export remains building.')
    replacement = ('240/240 prescribed exact Arena inputs confirmed, including the exact '
        'Navier–Stokes–Euler export. Final joined qualification: '
        f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}.")
    if old not in body:
        print('SKIPPED_DRAFT_UPDATE_TEXT_MOVED', flush=True)
        raise SystemExit(0)
    body = body.replace(old, replacement)
    body = body.replace('Draft pending the remaining Navier–Stokes–Euler qualification.',
        'All prescribed compatibility gates and matched Mathlib resource measurements pass. '
        'Official Arena hardware scoring remains outstanding; this proposal stays draft for review.')
    payload = out / 'draft-update.json'
    payload.write_text(json.dumps({'body': body}))
    note = subprocess.run(['gh', 'api', '--method', 'PATCH', f'repos/{REPO}/pulls/128',
        '--input', str(payload)], stdout=subprocess.DEVNULL)
    if note.returncode:
        print('DRAFT_NOTE_UNAVAILABLE_QUALIFICATION_ALREADY_WRITTEN', flush=True)
