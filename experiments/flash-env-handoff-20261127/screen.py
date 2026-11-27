"""Run the predeclared exact-prefix screen on four frozen executables."""
import os
from pathlib import Path

# Reuse the retained four-arm measurement harness, changing only identities and
# labels. The known-loop and prospective A/A threshold checks remain intact.
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/flash-skip-reuse-20261127/run_factorial.py').read_text()
source=source.replace("out = Path(__file__).resolve().parent / 'factorial'", "out = Path(os.environ.get('FLASH_HANDOFF_WORK','/tmp/flash-handoff-work')) / 'evidence' / 'screen'")
source=source.replace("bins = Path('/tmp/flash-skip-reuse-binaries')", "bins = Path(os.environ.get('FLASH_HANDOFF_WORK','/tmp/flash-handoff-work')) / 'evidence' / 'builds'")
source=source.replace("fixture = Path('/tmp/flash-mathlib-prefix-128m/mathlib-prefix-128m.ndjson')", "fixture = Path(os.environ.get('FLASH_HANDOFF_FIXTURE','/tmp/flash-runtime/mathlib-prefix.ndjson'))")
source=source.replace("client = Path('/tmp/flash-eval-front-counter.so')", "client = Path(os.environ.get('FLASH_HANDOFF_CLIENT','/workspace/scratch/f55dc021446a/diagnostics/counter-v1.so'))")
source=source.replace("drrun = Path('/tmp/flash-dynamorio/DynamoRIO-Linux-11.92.20777/bin64/drrun')", "drrun = Path(os.environ.get('FLASH_HANDOFF_DRRUN','/workspace/scratch/f55dc021446a/diagnostics/dynamorio/bin64/drrun'))")
source=source.replace("arms = ['baseline', 'skip', 'reuse', 'combined']", "arms = ['baseline', 'projection', 'frame-copy', 'combined']")
source=source.replace("assert sha(client) == '1b3c61f072436fd58606c84ff6198676cb194c47decc0a936cad1c74a35b26d9'", "assert sha(client) == '212a57d6dedc34155467d196e76d30b5d50ceb15010212c4c0f65dd6914194ce'")
exec(compile(source,str(__file__),'exec'))
