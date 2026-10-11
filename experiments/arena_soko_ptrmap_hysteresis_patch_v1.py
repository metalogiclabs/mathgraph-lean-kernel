#!/usr/bin/env python3
"""Pure capacity-policy experiment on source-pinned Soko PtrMap.

Only the shrink hysteresis threshold changes after a completely verified
cache reset. The underlying map, hash, slot representation and verifier
rules remain unchanged. Not warranted as a speedup until independent A/B.
"""
from pathlib import Path
import sys

source = Path(sys.argv[1]) / "src/checker/ptrmap.rs"
s = source.read_text()
old = "if self.tags.len() >= want * 4 {"
new = "if self.tags.len() >= want.saturating_mul(16) {"
assert s.count(old) == 1, "Pinned PtrMap shrink policy diverged"
assert "let n = self.tags.len() * 4;" in s, "Require tested 4x growth ancestor"
assert "self.shift -= 2;" in s, "Require exact growth shift"
s = s.replace(old, new)
assert s.count(new) == 1

# These tests guard that an old-session cached value is not visible after
# reset_shrink; they do not claim any performance improvement.
s += """
#[cfg(test)]
mod reset_hysteresis_tests {
    use super::*;

    #[test]
    fn old_session_keys_are_invisible_after_reset() {
        let mut m = PtrMap::<u64, u64>::with_cap(1);
        for i in 0..5000_u64 {
            m.insert(i, i.wrapping_mul(17));
        }
        for i in 0..5000_u64 {
            assert_eq!(m.get(&i), Some(i.wrapping_mul(17)));
        }
        m.reset_shrink();
        for i in 0..5000_u64 {
            assert_eq!(m.get(&i), None);
        }
        for i in 5000..10000_u64 {
            m.insert(i, i.wrapping_add(9));
        }
        for i in 5000..10000_u64 {
            assert_eq!(m.get(&i), Some(i.wrapping_add(9)));
        }
        for i in 0..5000_u64 {
            assert_eq!(m.get(&i), None);
        }
    }

    #[test]
    fn collision_and_repeated_shrink_preserve_exact_map_meaning() {
        let mut m = PtrMap::<u64, u64>::with_cap(0);
        for epoch in 0..8_u64 {
            for i in 0..2000_u64 {
                m.insert(i, epoch ^ (i << 1));
            }
            for i in 0..2000_u64 {
                assert_eq!(m.get(&i), Some(epoch ^ (i << 1)));
            }
            m.reset_shrink();
            for i in 0..2000_u64 {
                assert_eq!(m.get(&i), None);
            }
        }
    }
}
"""
source.write_text(s)
print("PTRMAP_SHRINK_HYSTERESIS_PATCH=4X_TO_16X_AFTER_4X_GROWTH", flush=True)
