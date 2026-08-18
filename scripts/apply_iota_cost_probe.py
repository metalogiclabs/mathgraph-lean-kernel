#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'eval.rs'
s = p.read_text()

anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

static MG_IOTA_FIRE_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_RULE_CACHE_HIT: AtomicU64 = AtomicU64::new(0);
static MG_RULE_CACHE