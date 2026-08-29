#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src" / "conv.rs"
MARKER = "DEVELOPMENTAL_CONV_TRACE_V1"

HELPER_ANCHOR = "fn rigid_head_eq<'a>(hx: RigidHead<'a>, hy: RigidHead<'a>) -> bool {"
HELPER = r'''
// DEVELOPMENTAL_CONV_TRACE_V1
#[inline]
fn developmental_conv_trace_enabled() -> bool {
    std::env::var_os("MATHGRAPH_CONV_TRACE").is_some()
}

#[inline]
fn developmental_conv_trace(
    depth: u32,
    left_len: usize,
    right_len: usize,
    left_hint_lt: bool,
    right_hint_lt: bool,
    left_unfoldable: bool,
    right_unfoldable: bool,
    baseline_action: &'static str,
) {
    if !developmental_conv_trace_enabled() {
        return;
    }
    eprintln!(
        concat!(
            "MATHGRAPH_CONV_TRACE {\"state\":{",
            "\"depth\":{},",
            "\"left_len\":{},\"right_len\":{},",
            "\"left_shorter\":{},\"right_shorter\":{},",
            "\"one_spine_is_one\":{},",
            "\"left_hint_lt\":{},\"right_hint_lt\":{},",
            "\"left_unfoldable\":{},\"right_unfoldable\":{}",
            "},\"baseline_action\":\"{}\"}"
        ),
        depth,
        left_len,
        right_len,
        left_len < right_len,
        right_len < left_len,
        left_len == 1 || right_len == 1,
        left_hint_lt,
        right_hint_lt,
        left_unfoldable,
        right_unfoldable,
        baseline_action,
    );
}

'''

DECISION_ANCHOR = """                    let lh = self.unfold_hint(nx);\n                    let rh = self.unfold_hint(ny);\n                    if lh.is_lt(&rh) {\n"""
DECISION_REPLACEMENT = """                    let lh = self.unfold_hint(nx);\n                    let rh = self.unfold_hint(ny);\n                    if developmental_conv_trace_enabled() {\n                        // Probe unfoldability without mutating scheduling: unfold_value is the same\n                        // operation the baseline immediately uses in each branch. The values are\n                        // discarded here; tracing is experimental-only and never enabled in K0.\n                        let lv = self.unfold_value(depth, t);\n                        let rv = self.unfold_value(depth, t2);\n                        let left_unfoldable = !std::ptr::eq(lv, t);\n                        let right_unfoldable = !std::ptr::eq(rv, t2);\n                        let baseline_action = if lh.is_lt(&rh) {\n                            \"unfold_right\"\n                        } else if rh.is_lt(&lh) {\n                            \"unfold_left\"\n                        } else {\n                            \"unfold_both\"\n                        };\n                        developmental_conv_trace(\n                            depth, sx.len(), sy.len(), lh.is_lt(&rh), rh.is_lt(&lh),\n                            left_unfoldable, right_unfoldable, baseline_action,\n                        );\n                    }\n                    if lh.is_lt(&rh) {\n"""


def main() -> None:
    text = PATH.read_text()
    if MARKER in text:
        print("trace instrumentation already present")
        return
    if HELPER_ANCHOR not in text:
        raise SystemExit("helper anchor missing")
    if DECISION_ANCHOR not in text:
        raise SystemExit("decision anchor missing")
    text = text.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    text = text.replace(DECISION_ANCHOR, DECISION_REPLACEMENT, 1)
    PATH.write_text(text)
    print(f"instrumented {PATH}")


if __name__ == "__main__":
    main()
