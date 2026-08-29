#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src" / "conv.rs"
MARKER = "DEVELOPMENTAL_CONV_FORCE_V1"
ANCHOR = """                    let lh = self.unfold_hint(nx);\n                    let rh = self.unfold_hint(ny);\n                    if lh.is_lt(&rh) {\n"""
REPLACEMENT = """                    let lh = self.unfold_hint(nx);\n                    let rh = self.unfold_hint(ny);\n                    // DEVELOPMENTAL_CONV_FORCE_V1\n                    // Experimental counterfactual only. Production behavior is unchanged unless\n                    // MATHGRAPH_CONV_FORCE_ACTION is explicitly set by the isolated runner.\n                    if let Ok(forced) = std::env::var(\"MATHGRAPH_CONV_FORCE_ACTION\") {\n                        match forced.as_str() {\n                            \"unfold_left\" => {\n                                let v1 = self.unfold_value(depth, t);\n                                if !std::ptr::eq(v1, t) {\n                                    return self.unify::<true>(depth, v1, t2);\n                                }\n                            }\n                            \"unfold_right\" => {\n                                let v2 = self.unfold_value(depth, t2);\n                                if !std::ptr::eq(v2, t2) {\n                                    return self.unify::<true>(depth, t, v2);\n                                }\n                            }\n                            \"unfold_both\" => {\n                                return self.unfold_pair(depth, t, t2);\n                            }\n                            \"baseline\" => {}\n                            _ => panic!(\"unknown MATHGRAPH_CONV_FORCE_ACTION={forced}\"),\n                        }\n                    }\n                    if lh.is_lt(&rh) {\n"""


def main() -> None:
    text = PATH.read_text()
    if MARKER in text:
        print("counterfactual instrumentation already present")
        return
    if ANCHOR not in text:
        raise SystemExit("decision anchor missing; run force injector on a clean checkout")
    PATH.write_text(text.replace(ANCHOR, REPLACEMENT, 1))
    print(f"counterfactual-instrumented {PATH}")


if __name__ == "__main__":
    main()
