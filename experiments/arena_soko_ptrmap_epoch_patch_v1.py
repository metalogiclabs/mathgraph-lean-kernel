#!/usr/bin/env python3
"""Experimental exact epoch tagging for PtrMap, replacing O(capacity) reset.
Preserve full hash and key equality checks, and clear on 8-bit epoch rollover.
Not a checker semantic rule; requires protected verdicts and regression tests.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/ptrmap.rs"
s=p.read_text()
def replace(old,new,n=1):
    global s
    assert s.count(old)==n,(old[:100],s.count(old),n)
    s=s.replace(old,new)
replace("tags: Vec<u8>,","tags: Vec<u16>,")
replace("shift: u32,\n    len: usize,","shift: u32,\n    epoch: u8,\n    len: usize,")
replace("const VACANT: u8 = 0;","const VACANT: u16 = 0;")
replace("fn place(&self, w: &K::Words) -> (usize, u8) {","fn place(&self, w: &K::Words) -> (usize, u16) {")
replace("let tag = ((h >> (self.shift - 7)) & 0x7f) as u8 | 0x80;",
        "let sig = ((h >> (self.shift - 7)) & 0x7f) as u16 | 0x80;\n        let tag = (u16::from(self.epoch) << 8) | sig;")
replace("pub(crate) fn find(&self, k: K) -> Result<V, (usize, u8)> {",
        "pub(crate) fn find(&self, k: K) -> Result<V, (usize, u16)> {")
replace("pub(crate) fn insert_at(&mut self, at: (usize, u8), k: K, v: V) {",
        "pub(crate) fn insert_at(&mut self, at: (usize, u16), k: K, v: V) {")
replace("} else if t == VACANT {","} else if t >> 8 != u16::from(self.epoch) {",2)
replace("if t == VACANT {\n                continue;","if t >> 8 != u16::from(self.epoch) {\n                continue;")
replace("while self.tags[i] != VACANT {","while self.tags[i] >> 8 == u16::from(self.epoch) {")
replace("shift: 64 - n.trailing_zeros(),\n            len: 0,",
        "shift: 64 - n.trailing_zeros(),\n            epoch: 1,\n            len: 0,")
replace("if self.len != 0 {\n            self.tags.fill(VACANT);\n            self.len = 0;\n        }",
"""if self.len != 0 {
            self.epoch = self.epoch.wrapping_add(1);
            // On wrap, physically erase every old generation before reusing 1.
            if self.epoch == 0 {
                self.tags.fill(VACANT);
                self.epoch = 1;
            }
            self.len = 0;
        }""")
s += """
#[cfg(test)]
mod epoch_reset_regressions {
    use super::*;
    #[test]
    fn epoch_wrap_does_not_resurrect_old_keys() {
        let mut m = PtrMap::<u64, u64>::with_cap(8);
        for generation in 0u64..600 {
            m.insert(111, generation);
            assert_eq!(m.get(&111), Some(generation));
            m.reset();
            assert_eq!(m.get(&111), None);
        }
    }
    #[test]
    fn repeated_resize_with_reset_preserves_key_identity() {
        let mut m = PtrMap::<u64, u64>::with_cap(8);
        for generation in 0u64..260 {
            for key in 0u64..400 {
                m.insert(key, generation ^ key);
            }
            for key in 0u64..400 {
                assert_eq!(m.get(&key), Some(generation ^ key));
            }
            m.reset();
            for key in 0u64..400 {
                assert_eq!(m.get(&key), None);
            }
        }
    }
}
"""
p.write_text(s)
print("PTRMAP_EPOCH_TAGGING=APPLIED_WRAP_SAFE",flush=True)
