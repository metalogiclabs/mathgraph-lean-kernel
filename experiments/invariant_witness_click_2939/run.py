#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/tmp/click-k-to-w')
REPRO = Path('/tmp/k_to_w_repro_click_2939.py')
SPEC = Path(__file__).with_name('WITNESS_SPEC_V1.json')
RESULT = Path(__file__).with_name('results.json')


def sh(cmd: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, cwd=cwd, shell=True, text=True, capture_output=True)
    if check and p.returncode != 0:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        raise SystemExit(p.returncode)
    return p


def write_repro() -> str:
    text = '''import click\nfrom click.testing import CliRunner\n\n@click.command()\n@click.argument("file_input", type=click.File("r"))\ndef cli(file_input):\n    for line in file_input.readlines():\n        print(line.rstrip())\n\nr = CliRunner().invoke(cli, ["-"], input="test\\n")\nprint(r.exit_code, repr(r.output))\nraise SystemExit(0 if r.exit_code == 0 and r.output == "test\\n" else 1)\n'''
    REPRO.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def clone():
    sh(f'rm -rf {ROOT}')
    sh(f'git clone --quiet --depth 1 --branch 8.2.1 https://github.com/pallets/click.git {ROOT}')
    sh("python -m pip install -q -e . 'pytest==8.3.5'", cwd=ROOT)


def patch_delete_only():
    p = ROOT / 'src/click/testing.py'
    s = p.read_text()
    old = '''    def __next__(self) -> str:  # type: ignore\n        try:\n            line = super().__next__()\n        except StopIteration as e:\n            raise EOFError() from e\n        return line\n\n'''
    assert old in s
    p.write_text(s.replace(old, '', 1))


def patch_witness_completed():
    patch_delete_only()
    p = ROOT / 'src/click/testing.py'
    s = p.read_text()
    old1 = '            val = next(text_input).rstrip("\\r\\n")\n'
    new1 = '''            try:\n                val = next(text_input).rstrip("\\r\\n")\n            except StopIteration as e:\n                raise EOFError() from e\n'''
    old2 = '            return next(text_input).rstrip("\\r\\n")\n'
    new2 = '''            try:\n                return next(text_input).rstrip("\\r\\n")\n            except StopIteration as e:\n                raise EOFError() from e\n'''
    assert old1 in s and old2 in s
    p.write_text(s.replace(old1, new1, 1).replace(old2, new2, 1))


def run_python(code: str) -> tuple[int, str]:
    q = sh("python - <<'PY'\n" + code + "\nPY", cwd=ROOT, check=False)
    return q.returncode, q.stdout + q.stderr


def witnesses(repro_hash: str) -> dict[str, bool]:
    w: dict[str, bool] = {}
    # R1 exact issue reproducer.
    p = sh(f'python {REPRO}', cwd=ROOT, check=False)
    w['R1_NATIVE_ITERATOR_EOF'] = p.returncode == 0

    code = r'''import click
from click.testing import CliRunner
@click.command()
@click.argument("f", type=click.File("r"))
def a(f):
    click.echo("|".join(x.rstrip() for x in f))
@click.command()
@click.argument("f", type=click.File("r"))
def b(f):
    click.echo("|".join(x.rstrip() for x in list(f)))
for cli in (a,b):
    r=CliRunner().invoke(cli,["-"],input="x\ny\n")
    assert r.exit_code==0 and r.output=="x|y\n", (r.exit_code,r.output)
'''
    w['R2_TEXTIO_ITERATION'] = run_python(code)[0] == 0

    code = r'''import click
from click.testing import CliRunner
@click.command()
def cli():
    click.prompt("value")
r=CliRunner().invoke(cli,[],input="")
assert r.exit_code == 1
assert isinstance(r.exception, SystemExit)
assert "Aborted!" in r.output
'''
    w['R3_INTERACTIVE_EOF'] = run_python(code)[0] == 0

    code = r'''import click, sys
from click.testing import CliRunner
@click.command()
def cli():
    click.echo(f"{sys.stdin.name}|{sys.stdin.mode}")
r=CliRunner().invoke(cli,[])
assert r.exit_code==0
assert r.output=="<stdin>|r\n"
'''
    w['R4_NAME_MODE'] = run_python(code)[0] == 0

    diff = sh('git diff -- src/click/testing.py', cwd=ROOT).stdout
    changed = sh('git diff --name-only', cwd=ROOT).stdout.splitlines()
    w['F1_NO_FILE_SPECIAL_CASE'] = changed == ['src/click/testing.py'] and 'click.File' not in diff
    w['F2_NO_COMMAND_EOF_MASK'] = changed == ['src/click/testing.py'] and w['R3_INTERACTIVE_EOF']
    text = (ROOT / 'src/click/testing.py').read_text()
    generic_override_absent = 'def __next__(self) -> str' not in text
    local_interactive = text.count('except StopIteration as e:') >= 2
    w['F3_NO_GLOBAL_EOF_CHANGE'] = generic_override_absent and local_interactive
    w['F4_NO_REPRO_PATCH'] = hashlib.sha256(REPRO.read_bytes()).hexdigest() == repro_hash
    return w


def evaluate_arm(name: str, patcher, repro_hash: str) -> dict:
    sh('git checkout -- src/click/testing.py', cwd=ROOT)
    patcher()
    ws = witnesses(repro_hash)
    return {
        'arm': name,
        'headline_closed': ws['R1_NATIVE_ITERATOR_EOF'],
        'witnesses': ws,
        'witness_pass_count': sum(ws.values()),
        'witness_total': len(ws),
        'admissible': all(ws.values()),
    }


def main():
    spec = json.loads(SPEC.read_text())
    ids = [c['id'] for c in spec['clauses']]
    assert len(ids) == len(set(ids)) == 8
    repro_hash = write_repro()
    clone()

    baseline = sh(f'python {REPRO}', cwd=ROOT, check=False)
    baseline_reproduced = baseline.returncode != 0
    if not baseline_reproduced:
        raise SystemExit('baseline did not reproduce issue')

    delete_only = evaluate_arm('O0_DELETE_GLOBAL_OVERRIDE_ONLY', patch_delete_only, repro_hash)
    completed = evaluate_arm('O1_WITNESS_COMPLETED_LOCAL_EOF_BOUNDARY', patch_witness_completed, repro_hash)

    # Exact upstream-unaffected verification for admitted arm.
    sh('git checkout -- src/click/testing.py', cwd=ROOT)
    patch_witness_completed()
    upstream = sh("pytest -q --ignore=tests/test_chain.py && pytest -q tests/test_chain.py -k 'not test_pipeline'", cwd=ROOT, check=False)
    upstream_unaffected = upstream.returncode == 0

    # Causal ablation restores original residual.
    sh('git checkout -- src/click/testing.py', cwd=ROOT)
    ab = sh(f'python {REPRO}', cwd=ROOT, check=False)
    ablation_restores = ab.returncode != 0

    result = {
        'protocol': 'K_TO_W_CLICK_2939_V1',
        'retrospective_module_test': True,
        'baseline_reproduced': baseline_reproduced,
        'O0_delete_only': delete_only,
        'O1_witness_completed': completed,
        'upstream_unaffected_tests_pass': upstream_unaffected,
        'ablation_restores_residual': ablation_restores,
    }
    result['pass'] = (
        delete_only['headline_closed']
        and not delete_only['admissible']
        and not delete_only['witnesses']['R3_INTERACTIVE_EOF']
        and completed['admissible']
        and upstream_unaffected
        and ablation_restores
    )
    result['verdict'] = 'K_TO_W_INVARIANT_WITNESS_COMPILATION_SUPPORTED' if result['pass'] else 'K_TO_W_RESIDUAL_REMAINS'
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result['pass']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
