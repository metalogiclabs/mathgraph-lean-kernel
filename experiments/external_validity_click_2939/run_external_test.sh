#!/usr/bin/env bash
set -euo pipefail

WORK="/tmp/click-external-validity"
rm -rf "$WORK"
git clone --quiet --depth 1 --branch 8.2.1 https://github.com/pallets/click.git "$WORK"
cd "$WORK"
python -m pip install -q -e . 'pytest==8.3.5'

cat > /tmp/repro_click_2939.py <<'PY'
import click
from click.testing import CliRunner

@click.command()
@click.argument("file_input", type=click.File("r"))
def cli(file_input):
    for line in file_input.readlines():
        print(line.rstrip())

r = CliRunner().invoke(cli, ["-"], input="test\n")
print(f"exit_code={r.exit_code}")
print(f"output={r.output!r}")
raise SystemExit(0 if (r.exit_code == 0 and r.output == "test\n") else 1)
PY

cat > /tmp/transfer_click_2939.py <<'PY'
import click
from click.testing import CliRunner

@click.command()
@click.argument("file_input", type=click.File("r"))
def iter_cli(file_input):
    for line in file_input:
        click.echo(f"I:{line.rstrip()}")

@click.command()
@click.argument("file_input", type=click.File("r"))
def list_cli(file_input):
    click.echo("|".join(x.rstrip() for x in list(file_input)))

for cli, inp, expected in [
    (iter_cli, "a\nb\n", "I:a\nI:b\n"),
    (list_cli, "x\ny\n", "x|y\n"),
]:
    r = CliRunner().invoke(cli, ["-"], input=inp)
    print(cli.name, r.exit_code, repr(r.output))
    assert r.exit_code == 0
    assert r.output == expected

# Source-distinct transfer into Click's chained-command architecture, matching the
# external suite's pipeline shape but using the corrected behavioral contract.
@click.group(chain=True, invoke_without_command=True)
@click.option("-f", type=click.File("r"))
def chain_cli(f):
    pass

@chain_cli.result_callback()
def process_pipeline(processors, f):
    iterator = (x.rstrip("\r\n") for x in f)
    for processor in processors:
        iterator = processor(iterator)
    for item in iterator:
        click.echo(item)

@chain_cli.command("uppercase")
def make_uppercase():
    def processor(iterator):
        for line in iterator:
            yield line.upper()
    return processor

@chain_cli.command("strip")
def make_strip():
    def processor(iterator):
        for line in iterator:
            yield line.strip()
    return processor

for args, inp, expected in [
    (["-f", "-"], "foo\nbar", "foo\nbar\n"),
    (["-f", "-", "strip"], "foo \n bar", "foo\nbar\n"),
    (["-f", "-", "strip", "uppercase"], "foo \n bar", "FOO\nBAR\n"),
]:
    r = CliRunner().invoke(chain_cli, args, input=inp)
    print("chain", args, r.exit_code, repr(r.output))
    assert r.exit_code == 0
    assert r.output == expected
    assert "Aborted!" not in r.output
PY

set +e
python /tmp/repro_click_2939.py > /tmp/baseline.txt 2>&1
BASE=$?
set -e
if [ "$BASE" -eq 0 ]; then
  echo "BASELINE_DID_NOT_REPRODUCE"
  cat /tmp/baseline.txt
  exit 2
fi
echo "BASELINE_REPRODUCED=1"
cat /tmp/baseline.txt

cp src/click/testing.py /tmp/testing.py.pristine

python - <<'PY'
from pathlib import Path
p = Path("src/click/testing.py")
s = p.read_text()
old = '''    def __next__(self) -> str:  # type: ignore\n        try:\n            line = super().__next__()\n        except StopIteration as e:\n            raise EOFError() from e\n        return line\n\n'''
if old not in s:
    raise SystemExit("FROZEN_OPERATOR_PATTERN_NOT_FOUND")
p.write_text(s.replace(old, "", 1))
PY

git diff -- src/click/testing.py
python /tmp/repro_click_2939.py | tee /tmp/intervention.txt
python /tmp/transfer_click_2939.py | tee /tmp/transfer.txt

echo "INTERVENTION_REPRO_PASS=1"
echo "TRANSFER_VARIANTS_PASS=1"

# External verifier. Run every upstream test except the single function whose
# 8.2.1 assertion explicitly encodes the bug (it strips the expected blank +
# 'Aborted!' suffix). Then run every other test in that same file.
pytest -q tests --ignore=tests/test_chain.py | tee /tmp/upstream_pytest.txt
pytest -q tests/test_chain.py -k 'not test_pipeline' | tee -a /tmp/upstream_pytest.txt

echo "UPSTREAM_UNAFFECTED_TESTS_PASS=1"

cp /tmp/testing.py.pristine src/click/testing.py
set +e
python /tmp/repro_click_2939.py > /tmp/ablation.txt 2>&1
ABL=$?
set -e
if [ "$ABL" -eq 0 ]; then
  echo "ABLATION_FAILED_TO_RESTORE_RESIDUAL"
  cat /tmp/ablation.txt
  exit 3
fi
echo "ABLATION_RESTORES_RESIDUAL=1"
cat /tmp/ablation.txt

cat > /tmp/external_validity_result.json <<JSON
{
  "external_repo": "pallets/click",
  "external_ref": "8.2.1",
  "issue": 2939,
  "baseline_reproduced": true,
  "intervention_reproducer_pass": true,
  "source_distinct_transfer_pass": true,
  "chain_pipeline_corrected_contract_pass": true,
  "all_unaffected_upstream_tests_pass": true,
  "ablation_restores_residual": true,
  "verdict": "EXTERNAL_CAUSAL_TRANSFER_SUPPORTED"
}
JSON
cat /tmp/external_validity_result.json
