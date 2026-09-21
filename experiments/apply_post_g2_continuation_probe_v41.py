from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_post_g2_continuation_probe_v41.py G2_SELECTION_JSON")

selection = json.loads(Path(sys.argv[1]).read_text())
winner = selection["winner_materializer"]
if winner not in {"pi", "inductive"}:
    raise SystemExit("V41_BAD_G2_WINNER")

p = Path("src/infer.rs")
s = p.read_text()

import_anchor = "use InferFlag::*;\n"
assert import_anchor in s
s = s.replace(
    import_anchor,
    import_anchor + "use std::sync::atomic::{AtomicU64, Ordering};\n"
    + "pub static V41_G3_TOTAL: AtomicU64 = AtomicU64::new(0);\n"
    + "pub static V41_G3_DIRECT: AtomicU64 = AtomicU64::new(0);\n",
    1,
)

if winner == "pi":
    required = """        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        while let Some(arg) = args.pop() {
            let fty_f = if direct_pi { fty } else { self.force_all(depth, fty) };
"""
    if required not in s:
        raise SystemExit("V41_RHO3_NOT_DERIVABLE_BEFORE_G2")

    repl = """        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        let mut v41_seen_first = false;
        while let Some(arg) = args.pop() {
            if v41_seen_first {
                V41_G3_TOTAL.fetch_add(1, Ordering::Relaxed);
                if !direct_pi && matches!(fty, Value::Pi { .. }) {
                    V41_G3_DIRECT.fetch_add(1, Ordering::Relaxed);
                }
            }
            let fty_f = if direct_pi { fty } else { self.force_all(depth, fty) };
            v41_seen_first = true;
"""
    s = s.replace(required, repl, 1)

else:
    required = """        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let struct_ty = cap.value;
        let struct_ty_f = if cap.inductive_direct { struct_ty } else { self.force_all(depth, struct_ty) };
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    if required not in s:
        raise SystemExit("V41_RHO3_NOT_DERIVABLE_BEFORE_G2")

    repl = """        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let struct_ty = cap.value;
        let struct_ty_f = if cap.inductive_direct { struct_ty } else { self.force_all(depth, struct_ty) };
        let v41_outer_direct = cap.inductive_direct;
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    s = s.replace(required, repl, 1)

    start = s.index("    fn infer_proj_v(")
    end = s.index("    pub(crate) fn check_declar_info_v", start)
    block = s[start:end]
    needle = "match self.force_all(depth, cur) {"
    count = block.count(needle)
    if count < 1:
        raise SystemExit("V41_G3_PROJECTION_CONTINUATION_ANCHOR_MISSING")
    replacement = """{
                V41_G3_TOTAL.fetch_add(1, Ordering::Relaxed);
                if v41_outer_direct && matches!(cur, Value::Pi { .. }) {
                    V41_G3_DIRECT.fetch_add(1, Ordering::Relaxed);
                }
                match self.force_all(depth, cur) {"""
    block = block.replace(needle, replacement)
    # Every inserted block opens one extra brace.
    block = block.replace(
        """                _ => panic!("ran out of param telescope in projection"),
            }
""",
        """                _ => panic!("ran out of param telescope in projection"),
                }
            }
""",
    )
    block = block.replace(
        """                _ => panic!("ran out of constructor telescope in projection"),
            }
""",
        """                _ => panic!("ran out of constructor telescope in projection"),
                }
            }
""",
    )
    block = block.replace(
        """            _ => panic!("ran out of constructor telescope getting projection field"),
        }
""",
        """            _ => panic!("ran out of constructor telescope getting projection field"),
            }
        }
""",
    )
    s = s[:start] + block + s[end:]

p.write_text(s)

m = Path("src/main.rs")
ms = m.read_text()
use_anchor = "use sokonanoda::util::Config;\n"
assert use_anchor in ms
ms = ms.replace(
    use_anchor,
    use_anchor
    + "use sokonanoda::infer::{V41_G3_TOTAL, V41_G3_DIRECT};\n"
    + "use std::sync::atomic::Ordering;\n",
    1,
)
check_anchor = """    export_file.check_all_declars();
    // Pretty print as necessary
"""
assert check_anchor in ms
check_repl = f"""    export_file.check_all_declars();
    eprintln!(
        "MSI_V41_G3 winner={winner} total={{}} direct={{}}",
        V41_G3_TOTAL.load(Ordering::Relaxed),
        V41_G3_DIRECT.load(Ordering::Relaxed),
    );
    // Pretty print as necessary
"""
ms = ms.replace(check_anchor, check_repl, 1)
m.write_text(ms)

print("V41_RHO3_POST_G2_PROBE_INSTALLED", winner)
