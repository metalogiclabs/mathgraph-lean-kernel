"""Instrument the rejected alias source, without changing its cache decisions.

Run only in a disposable checkout of 492480f59fbdfebaa80180ead495ff4fe143d4c6. Counter overhead means this binary
is for work counts, never performance measurement or release qualification.
"""
import argparse
from pathlib import Path


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkout", type=Path)
    root = p.parse_args().checkout
    path = root / "src/eval.rs"
    text = path.read_text()
    text = '''use std::sync::atomic::{AtomicU64, Ordering};
static EARLY_COUNTS: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
pub fn census_counts() -> [u64; 5] {
    std::array::from_fn(|i| EARLY_COUNTS[i].load(Ordering::Relaxed))
}
''' + text
    text = replace_once(text,
        "if let Some(v) = self.tc_cache.open_eval_cache.get(&original_key) {\n                return v;",
        "if let Some(v) = self.tc_cache.open_eval_cache.get(&original_key) {\n                EARLY_COUNTS[0].fetch_add(1, Ordering::Relaxed);\n                return v;")
    text = replace_once(text,
        "let v = match cached {\n                Some(v) => v,\n                None => {",
        "let v = match cached {\n                Some(v) => { EARLY_COUNTS[1].fetch_add(1, Ordering::Relaxed); v },\n                None => {\n                    EARLY_COUNTS[2].fetch_add(1, Ordering::Relaxed);")
    text = replace_once(text,
        "if original_key != key {\n                self.tc_cache.open_eval_cache.insert(original_key, v);\n            }",
        "if original_key != key {\n                EARLY_COUNTS[3].fetch_add(1, Ordering::Relaxed);\n                self.tc_cache.open_eval_cache.insert(original_key, v);\n            } else {\n                EARLY_COUNTS[4].fetch_add(1, Ordering::Relaxed);\n            }")
    path.write_text(text)
    path = root / "src/main.rs"
    text = replace_once(path.read_text(), "    export_file.check_all_declars();",
        '    export_file.check_all_declars();\n    eprintln!("EARLY_EVAL_CENSUS {:?}", sokonanoda::eval::census_counts());')
    path.write_text(text)


if __name__ == "__main__":
    main()
