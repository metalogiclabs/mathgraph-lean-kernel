"""Reuse exact-input raw-verdict qualification with explicit worker count."""
import hashlib
import os
from pathlib import Path

root=Path(__file__).resolve().parents[2]
path=root/'experiments/flash-upstream-repair-20261126/verify.py'
source=path.read_text()
threads=int(os.environ.get('STRICT_THREADS','2'));assert threads in (1,2)
old="args = ['--stdin', '--threads', '1', '--nat-extension', '--string-extension', '--axiom-allow-all']"
assert source.count(old)==1
source=source.replace(old,old.replace("'1'",repr(str(threads))))
assert source.count("'threads': 1")==2
source=source.replace("'threads': 1","'threads': "+str(threads))
exec(compile(source,str(__file__),'exec'))
