"""Reuse full-input comparators with baseline=2 and explicit candidate workers."""
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[2]
mode=sys.argv.pop(1);assert mode in ('native','instructions')
workers=int(os.environ.get('STRICT_THREADS','2'));assert workers in (1,2)
name='whole_native.py' if mode=='native' else 'compare_instructions.py'
source=(root/'experiments/flash-session-budget-20261126'/name).read_text()
old="'--stdin', '--threads', '2'"
assert source.count(old)==1
source=source.replace(old,"'--stdin', '--threads', (str("+str(workers)+") if name == 'strict' else '2')")
assert source.count("'threads': 2")==1
source=source.replace("'threads': 2","'threads': {'baseline': 2, 'strict': "+str(workers)+"}")
exec(compile(source,str(__file__),'exec'))
