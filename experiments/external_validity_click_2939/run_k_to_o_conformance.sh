#!/usr/bin/env bash
set -euo pipefail

WORK=/tmp/click-k-to-o
rm -rf "$WORK"
git clone -q --depth 1 --branch 8.2.1 https://github.com/pallets/click.git "$WORK"
cd "$WORK"
python -m pip install -q -e . pytest

# Apply O_v2. This experiment is NOT blind patch reconstruction: the upstream
# patch was inspected after the frozen V1 run. The purpose here is to test the
# newly identified K->O conformance / invariant-witness module.
python - <<'PY'
from pathlib import Path
p=Path('src/click/testing.py')
s=p.read_text()
old='''    def __next__(self) -> str:  # type: ignore\n        try:\n            line = super().__next__()\n        except StopIteration as e:\n            raise EOFError() from e\n        return line\n'''
assert old in s
s=s.replace(old,'')
oldv='''            val = next(text_input).rstrip("\\r\\n")'''
newv='''            try:\n                val = next(text_input).rstrip("\\r\\n")\n            except StopIteration as e:\n                raise EOFError() from e'''
assert oldv in s
s=s.replace(oldv,newv,1)
oldh='''            return next(text_input).rstrip("\\r\\n")'''
newh='''            try:\n                return next(text_input).rstrip("\\r\\n")\n            except StopIteration as e:\n                raise EOFError() from e'''
assert oldh in s
s=s.replace(oldh,newh,1)
p.write_text(s)
PY

# K1/K2: native iterator exhaustion and ordinary file iteration/readlines.
python - <<'PY'
import io
from click.testing import _NamedTextIOWrapper
b=io.BytesIO(b'a\nb\n')
t=io.TextIOWrapper(b, encoding='utf-8')
w=_NamedTextIOWrapper(t, name='<stdin>', mode='r')
assert list(w)==['a\n','b\n']
try:
    next(w)
except StopIteration:
    pass
else:
    raise AssertionError('K1 violated: iterator EOF did not remain StopIteration')
PY

# K4: isolated stream metadata remains intact.
python - <<'PY'
import io
from click.testing import _NamedTextIOWrapper
w=_NamedTextIOWrapper(io.TextIOWrapper(io.BytesIO(b''),encoding='utf-8'),name='<stdin>',mode='r')
assert w.name == '<stdin>'
assert w.mode == 'r'
PY

# K3 + forbidden constraints: command/file behavior is not patched to mask the
# issue. Verify the real regression reproducer now succeeds through the harness.
cat >/tmp/k_repro.py <<'PY'
import click
from click.testing import CliRunner
@click.command()
@click.argument('files', type=click.File('r'), nargs=-1)
def cli(files):
    for f in files:
        for line in f.readlines():
            click.echo(line.rstrip())
r=CliRunner().invoke(cli,['-'],input='one\ntwo\n')
assert r.exit_code == 0, (r.exit_code,r.output,r.exception)
assert r.output.splitlines()==['one','two']
PY
python /tmp/k_repro.py

# Critical invariant missed by O_v1: interactive EOF must still have interactive
# EOF semantics. Exercise both visible and hidden prompt paths through public API.
python - <<'PY'
import click
from click.testing import CliRunner

@click.command()
def visible():
    click.prompt('Name')
r=CliRunner().invoke(visible, input='')
assert r.exit_code != 0
assert isinstance(r.exception, SystemExit)
assert 'Aborted!' in r.output

@click.command()
def hidden():
    click.prompt('Secret', hide_input=True)
r=CliRunner().invoke(hidden, input='')
assert r.exit_code != 0
assert isinstance(r.exception, SystemExit)
assert 'Aborted!' in r.output
PY

# Regression + broad conformance. The historical chain expectation in 8.2.1 is
# known to encode the regression, so exclude only that single stale assertion.
pytest -q tests/test_testing.py tests/test_arguments.py tests/test_options.py >/tmp/k_conformance_pytest.txt
pytest -q tests/test_chain.py -k 'not test_pipeline_with_file' >>/tmp/k_conformance_pytest.txt

echo 'K_TO_O_CONFORMANCE_SUPPORTED'
