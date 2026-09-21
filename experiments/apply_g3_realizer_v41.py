from pathlib import Path
import json
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_g3_realizer_v41.py G3_SELECTION_JSON MODE")

selection = json.loads(Path(sys.argv[1]).read_text())
mode = sys.argv[2]
if mode not in {"shared", "sham"}:
    raise SystemExit("V41_BAD_G3_MODE")

materializer = selection["winner_materializer"]
if materializer not in {"pi_continuation", "inductive_telescope_continuation"}:
    raise SystemExit("V41_BAD_G3_MATERIALIZER")

p = Path("src/infer.rs")
s = p.read_text()

import_anchor = "use InferFlag::*;\n"
assert import_anchor in s
s = s.replace(
    import_anchor,
    import_anchor + "use std::sync::atomic::{AtomicU64, Ordering};\n"
    + "pub static V41_K3_OPP: AtomicU64 = AtomicU64::new(0);\n"
    + "pub static V41_K3_BYPASS: AtomicU64 = AtomicU64::new(0);\n",
    1,
)

if materializer == "pi_continuation":
    required = """        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        while let Some(arg) = args.pop() {
            let fty_f = if direct_pi { fty } else { self.force_all(depth, fty) };
"""
    if required not in s:
        raise SystemExit("V41_K3_REQUIRES_G2_PI_REALIZER")

    if mode == "shared":
        repl = """        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        let mut v41_seen_first = false;
        while let Some(arg) = args.pop() {
            let v41_k3_direct = v41_seen_first && matches!(fty, Value::Pi { .. });
            if v41_k3_direct {
                V41_K3_OPP.fetch_add(1, Ordering::Relaxed);
                V41_K3_BYPASS.fetch_add(1, Ordering::Relaxed);
            }
            let fty_f = if direct_pi || v41_k3_direct { fty } else { self.force_all(depth, fty) };
            v41_seen_first = true;
"""
    else:
        repl = """        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        let mut v41_seen_first = false;
        while let Some(arg) = args.pop() {
            let v41_k3_direct = v41_seen_first && matches!(fty, Value::Pi { .. });
            if v41_k3_direct {
                V41_K3_OPP.fetch_add(1, Ordering::Relaxed);
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
        raise SystemExit("V41_K3_REQUIRES_G2_INDUCTIVE_REALIZER")

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
    if needle not in block:
        raise SystemExit("V41_K3_PROJECTION_CONTINUATION_ANCHOR_MISSING")

    if mode == "shared":
        replacement = """match {
                let v41_k3_direct = v41_outer_direct && matches!(cur, Value::Pi { .. });
                if v41_k3_direct {
                    V41_K3_OPP.fetch_add(1, Ordering::Relaxed);
                    V41_K3_BYPASS.fetch_add(1, Ordering::Relaxed);
                    cur
                } else {
                    self.force_all(depth, cur)
                }
            } {"""
    else:
        replacement = """match {
                let v41_k3_direct = v41_outer_direct && matches!(cur, Value::Pi { .. });
                if v41_k3_direct {
                    V41_K3_OPP.fetch_add(1, Ordering::Relaxed);
                }
                self.force_all(depth, cur)
            } {"""

    block = block.replace(needle, replacement)
    s = s[:start] + block + s[end:]

p.write_text(s)

m = Path("src/main.rs")
ms = m.read_text()
use_anchor = "use sokonanoda::util::Config;\n"
assert use_anchor in ms
ms = ms.replace(
    use_anchor,
    use_anchor
    + "use sokonanoda::infer::{V41_K3_OPP, V41_K3_BYPASS};\n"
    + "use std::sync::atomic::Ordering;\n",
    1,
)
check_anchor = """    export_file.check_all_declars();
    // Pretty print as necessary
"""
assert check_anchor in ms
check_repl = f"""    export_file.check_all_declars();
    eprintln!(
        "MSI_V41_K3 mode={mode} opportunities={{}} bypasses={{}}",
        V41_K3_OPP.load(Ordering::Relaxed),
        V41_K3_BYPASS.load(Ordering::Relaxed),
    );
    // Pretty print as necessary
"""
ms = ms.replace(check_anchor, check_repl, 1)
m.write_text(ms)

print("V41_K3_REALIZER_MATERIALIZED", materializer, mode)
