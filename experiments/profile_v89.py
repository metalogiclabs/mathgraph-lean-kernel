#!/usr/bin/env python3
"""Frozen PGO wall-time and CPU-sampling comparison. Never promotes a checker."""
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
LLVM = 'github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#llvmPackages_21.llvm'
WORKSPACE = Path(os.environ.get('GITHUB_WORKSPACE', Path(__file__).resolve().parents[1]))
ROOT = Path(os.environ.get('V89_ROOT', '/tmp/v89'))
OUT = ROOT / 'out'
CONFIG = {'use_stdin': True, 'nat_extension': True, 'string_extension': True,
          'unpermitted_axiom_hard_error': False, 'unsafe_permit_all_axioms': True,
          'num_threads': 4, 'print_success_message': False}
KNOWN = {'tests::util::reject_rec_rule_with_forged_lambda_domains',
         'tests::util::reject_unlisted_recursor'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def save(obj, name='summary.json'):
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')

def call(cmd, *, cwd=None, env=None, log=None, check=True, timeout=3600):
    if log:
        with (OUT / log).open('wb') as f:
            p = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    else:
        p = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f'{cmd[0]} failed ({p.returncode}); {log or cmd}')
    return p.returncode

def capture(cmd, *, cwd=None, env=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)

def run_binary(binary, corpus, tag, prefix=None, timeout=1200):
    data = ROOT / 'arena' / '_build' / 'tests' / (corpus + '.ndjson')
    with data.open('rb') as inp, (OUT / f'{corpus}.{tag}.stdout').open('wb') as stdout, (OUT / f'{corpus}.{tag}.stderr').open('wb') as stderr:
        cmd = ([*prefix, '--'] if prefix else []) + [str(binary), str(ROOT / 'config.json')]
        start = time.perf_counter()
        p = subprocess.run(cmd, stdin=inp, stdout=stdout, stderr=stderr, timeout=timeout)
        seconds = time.perf_counter() - start
    return {'rc': p.returncode, 'seconds': seconds,
            'stdout_sha256': sha((OUT / f'{corpus}.{tag}.stdout').read_bytes()),
            'stderr_sha256': sha((OUT / f'{corpus}.{tag}.stderr').read_bytes())}

def parse_stacks(text):
    """Count one leaf per perf event, never every frame as a separate sample."""
    counts = Counter()
    total = 0
    pending = False
    header = re.compile(r'^\S+\s+\d+(?:/\d+)?\s+(?:\[\d+\]\s+)?\d+(?:\.\d+)?:')
    frame = re.compile(r'^\s+[0-9a-fA-F]+\s+(.+?)\s+\(')
    for line in text.splitlines():
        if header.match(line):
            total += 1
            counts['<unresolved>'] += 1
            pending = True
        elif pending:
            m = frame.match(line)
            if m:
                symbol = m.group(1).rsplit('+0x', 1)[0]
                counts['<unresolved>'] -= 1
                counts[symbol] += 1
                pending = False
    counts += Counter()
    assert total == sum(counts.values())
    return total, counts

def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):
            h.update(part)
    return h.hexdigest()

def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    source = WORKSPACE / 'experiments' / 'patch_prune_dm_v88.py'
    assert blob(source.read_bytes()) == '30ea00d0804d6b3be78df65914335e130ebe77f1'
    sys.path.insert(0, str(WORKSPACE / 'experiments'))
    import patch_prune_dm_v88 as patcher
    assert not (ROOT / 'control').exists(), 'Use a fresh V89_ROOT'
    call(['git', 'clone', '-q', 'https://github.com/metalogiclabs/mathgraph-lean-kernel', str(ROOT / 'control')])
    call(['git', '-C', str(ROOT / 'control'), 'checkout', '-q', BASE])
    shutil.copytree(ROOT / 'control', ROOT / 'candidate', ignore=shutil.ignore_patterns('.git', 'target'))
    old = (ROOT / 'control/src/util.rs').read_bytes()
    patcher.apply(ROOT / 'candidate', with_tests=False)
    assert (ROOT / 'candidate/src/util.rs').read_text() == patcher.transform(old.decode())
    import difflib
    (OUT / 'production.patch').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),
        (ROOT / 'candidate/src/util.rs').read_text().splitlines(True), fromfile='control/src/util.rs', tofile='candidate/src/util.rs')))
    assert (ROOT / 'control/src/tests.rs').read_bytes() == (ROOT / 'candidate/src/tests.rs').read_bytes()
    call(['git', 'clone', '-q', 'https://github.com/leanprover/lean-kernel-arena', str(ROOT / 'arena')])
    call(['git', '-C', str(ROOT / 'arena'), 'checkout', '-q', ARENA])
    assert capture(['git', '-C', str(ROOT / 'arena'), 'rev-parse', 'HEAD']).stdout.decode().strip() == ARENA
    save({'base': BASE, 'arena': ARENA, 'source_commit': os.environ.get('GITHUB_SHA'),
          'source_hashes': {arm: {p: blob((ROOT / arm / p).read_bytes()) for p in ['src/util.rs','src/eval.rs','src/tests.rs','Cargo.lock']}
                            for arm in ['control','candidate']},
          'source_change': 'retain_prune_dm_until_clear_session_ONLY'}, 'source.json')
    (ROOT / 'config.json').write_text(json.dumps(CONFIG) + '\n')
    for corpus in ['init-prelude','cedar','mathlib']:
        call(['./lka.py', 'build-test', corpus], cwd=ROOT / 'arena', log=f'build-{corpus}.log')
    save({c: sha_file(ROOT / 'arena/_build/tests' / (c+'.ndjson')) for c in ['init-prelude','cedar','mathlib']}, 'inputs.json')

def qualification():
    import check_test_results_v88 as q
    result = {'release_qualified': False}
    for arm in ['control','candidate']:
        env = dict(os.environ, CARGO_TARGET_DIR=str(ROOT / ('target-'+arm)), RUSTFLAGS='-C target-cpu=native')
        rc = call(['cargo','test','--locked'], cwd=ROOT/arm, env=env, log=f'{arm}.tests.log', check=False)
        text = (OUT / f'{arm}.tests.log').read_text()
        parsed = q.parse(text, 42)
        assert set(parsed['failures']) == KNOWN and rc == 101
        result[arm] = {**parsed, 'rc':rc}
    result['no_new_test_failures'] = True
    save(result, 'qualification.json')
    print('V89_NO_NEW_TEST_FAILURES=PASS', flush=True)
    print('V89_RELEASE_QUALIFICATION=BLOCKED_KNOWN_FIXTURES', flush=True)

def build_pgo(arm):
    root = ROOT / arm
    target = ROOT / ('target-'+arm)
    pgo = ROOT / ('pgo-'+arm)
    pgo.mkdir()
    common = '-C target-cpu=native -C debuginfo=1 -C force-frame-pointers=yes'
    env = dict(os.environ, CARGO_TARGET_DIR=str(target), RUSTFLAGS=common+' -C profile-generate='+str(pgo))
    call(['cargo','build','--release','--locked','-q'], cwd=root, env=env, log=f'{arm}.pgo-build.log')
    run_binary(target/'release/sokonanoda', 'init-prelude', arm+'.pgo')
    call(['nix','shell',LLVM,'-c','llvm-profdata','merge','-o',str(pgo/'merged.profdata'),str(pgo)], log=f'{arm}.profdata.log')
    assert (pgo/'merged.profdata').stat().st_size > 0
    env['RUSTFLAGS'] = common+' -C profile-use='+str(pgo/'merged.profdata')
    call(['cargo','build','--release','--locked','-q'], cwd=root, env=env, log=f'{arm}.release-build.log')
    binary = ROOT / (arm+'-checker')
    shutil.copy2(target/'release/sokonanoda', binary)
    return {'path':str(binary),'sha256':sha_file(binary),'flags':env['RUSTFLAGS'],
            'training_input':'init-prelude','profile_sha256':sha_file(pgo/'merged.profdata')}

def measure(binaries, summary):
    deltas = []
    for corpus in ['init-prelude','cedar','mathlib']:
        key = 'std' if corpus == 'init-prelude' else corpus
        entry = {'runs': []}
        summary['corpora'][key] = entry
        ref = run_binary(binaries['control']['path'], corpus, key+'.reference')
        cand = run_binary(binaries['candidate']['path'], corpus, key+'.candidate')
        assert ref['rc'] == cand['rc'] == 0
        assert ref['stdout_sha256'] == cand['stdout_sha256'] and ref['stderr_sha256'] == cand['stderr_sha256']
        entry.update(reference=ref, candidate=cand, exact_replay='PASS')
        save(summary)
        for i in range(5):
            for arm in (['control','candidate'] if i%2 == 0 else ['candidate','control']):
                row = run_binary(binaries[arm]['path'], corpus, f'{key}.{arm}.{i}')
                assert row['rc'] == 0
                assert row['stdout_sha256'] == ref['stdout_sha256'] and row['stderr_sha256'] == ref['stderr_sha256']
                entry['runs'].append({'pass':i,'arm':arm,**row})
                save(summary)
        a,b = [statistics.median(r['seconds'] for r in entry['runs'] if r['arm']==arm) for arm in ['control','candidate']]
        delta = 100*(b/a-1)
        entry.update(control_median=a,candidate_median=b,delta_percent=delta)
        deltas.append(delta)
        print(f'V89_{key.upper()}_DELTA_PERCENT={delta:.4f}',flush=True)
        save(summary)
    summary['geomean_delta_percent'] = 100*(math.prod(1+d/100 for d in deltas)**(1/len(deltas))-1)
    summary['timing_decision'] = 'REJECT_OR_INCONCLUSIVE' if summary['geomean_delta_percent'] >= -1 or max(deltas)>0 else 'REPEAT_AND_ABLATE'
    save(summary)

def profile(binaries, summary):
    perf = shutil.which('perf')
    assert perf, 'perf is not on the pinned toolchain PATH'
    probe = [perf,'record','-q','-e','cpu-clock:u','-F','99','-g','--call-graph','fp','-o',str(ROOT/'probe.data'),'--','/bin/true']
    rc = call(probe,log='probe.log',check=False)
    if rc:
        call(['sudo','-n','sysctl','-w','kernel.perf_event_paranoid=1'],log='perf-permission.log',check=False)
        rc = call(probe,log='probe-retry.log',check=False)
    if rc:
        summary['profile_status']='INFRASTRUCTURE_PERF_DENIED'
        save(summary)
        return
    summary['profiles']={}
    for corpus in ['cedar','mathlib']:
        for repeat in range(2):
            for arm in (['control','candidate'] if repeat%2==0 else ['candidate','control']):
                tag=f'{corpus}.{arm}.{repeat}'
                data=ROOT/(tag+'.data')
                prefix=[perf,'record','-q','-e','cpu-clock:u','-F','99','-g','--call-graph','fp','-o',str(data)]
                row=run_binary(binaries[arm]['path'],corpus,tag+'.sampled',prefix=prefix)
                assert row['rc']==0
                reference=summary['corpora'][corpus]['reference']
                assert row['stdout_sha256']==reference['stdout_sha256'] and row['stderr_sha256']==reference['stderr_sha256']
                call([perf,'report','-i',str(data),'--stdio','--no-children','--sort','symbol,dso','--percent-limit','0'],log=tag+'.report.txt')
                p=capture([perf,'script','-i',str(data)],timeout=120)
                assert p.returncode==0
                (OUT/(tag+'.stacks.txt')).write_bytes(p.stdout)
                n,counts=parse_stacks(p.stdout.decode(errors='replace'))
                if not n:
                    raise RuntimeError('Perf recorded zero samples: '+tag)
                summary['profiles'][tag]={'samples':n,'wall_seconds':row['seconds'],
                    'self_counts':dict(counts.most_common()),'input_sha256':sha_file(ROOT/'arena/_build/tests'/(corpus+'.ndjson')),
                    'binary_sha256':binaries[arm]['sha256']}
                save(summary)
                print(f'V89_PROFILE={tag} SAMPLES={n}',flush=True)
    summary['profile_status']='CPU_SAMPLES_RECORDED'
    save(summary)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    summary={'schema':1,'status':'IN_PROGRESS','release_promoted':False,
             'base':BASE,'arena':ARENA,'build':'native-fresh-pgo-debug-frame-pointers-4threads','corpora':{}}
    save(summary)
    try:
        prepare()
        qualification()
        binaries={arm:build_pgo(arm) for arm in ['control','candidate']}
        assert binaries['control']['sha256'] != binaries['candidate']['sha256']
        summary['binaries']=binaries
        save(summary)
        measure(binaries,summary)
        profile(binaries,summary)
        summary['status']='COMPLETE'
        summary['decision']='DIAGNOSTIC_ONLY__NO_RELEASE_PROMOTION'
    except BaseException as e:
        summary['status']='FAILED'
        summary['error']=repr(e)
        save(summary)
        raise
    save(summary)
    print('V89_GEOMEAN_DELTA_PERCENT=%.4f'%summary['geomean_delta_percent'],flush=True)
    print('V89_PROFILE_STATUS='+summary['profile_status'],flush=True)
    print('DECISION='+summary['decision'],flush=True)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        sample='profile.bin  123  1.25: 101 cpu-clock:u:\n\tabc target+0x1 (/tmp/profile.bin)\n\tdef caller+0x2 (/tmp/profile.bin)\n\nprofile.bin  123  1.26: 101 cpu-clock:u:\n\t123 other+0x2 (/tmp/profile.bin)\n'
        n,c=parse_stacks(sample)
        assert n==2 and c=={'target':1,'other':1}, (n,c)
        print('V89_PARSER_SELF_TEST=PASS')
    else:
        main()
