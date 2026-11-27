"""Prospective extra-component test on the measured two-worker source stack.

Hypothesis 1: canonical environment handoff changes cache demand; reducing the
exact-key prune memo from 256 KiB to 64 KiB per worker may improve locality.
The prior isolated 4K result is not evidence for this new combination.
Hypothesis 2: selective infer_nonvar inlining may remove call/node dispatch
overhead, at the risk of larger code and slower instruction-cache behavior.
Test each addition and both, preserving every source-record and type check.
The shared screen fixes the incremental threshold from repeated unchanged
baseline/stack controls before these candidates are measured. Full-input,
wall-time and broad correctness gates remain separate; no percentage forecast.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build as b
original=b.configure
def configure(source,features):
 original(source,features)
 if features.get('prune_bits'):
  bits=features['prune_bits'];p=source/'src/checker/cache.rs'
  b.replace(p,'pub(crate) const PRUNE_DM_LEN: usize = 1 << 14;',f'pub(crate) const PRUNE_DM_LEN: usize = 1 << {bits};')
  b.replace(p,'pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 14;',f'pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - {bits};')
 if features.get('inline_infer'):
  b.replace(source/'src/checker/infer.rs','    #[inline(never)]\n    fn infer_nonvar(','    #[inline(always)]\n    fn infer_nonvar(')
b.configure=configure
base=dict(b.ARMS['pib36'])
arms={'stack-prune4':dict(base,prune_bits=12),'stack-infer':dict(base,inline_infer=True),'stack-both':dict(base,prune_bits=12,inline_infer=True)}
b.save(b.OUT/'remaining-overhead-protocol.json',{'state':'PROSPECTIVE_BEFORE_CANDIDATE_MEASUREMENTS','parent':'stack-control','features':arms,'source_control':'same source path, explicit x86_64 target, compiler flags and frozen executable guards','cost_gate':'Two alternating pairs and aggregate must each beat the pre-measured max(1%, twice larger baseline/parent identical-executable range).','boundary':'Exact prefix only; no score or elapsed-speed forecast. Keep two workers; no check is removed.'})
for arm,features in arms.items():b.build(arm,features,target='x86_64-unknown-linux-gnu')
