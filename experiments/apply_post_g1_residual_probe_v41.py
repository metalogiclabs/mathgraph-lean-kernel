from pathlib import Path

p = Path("src/infer.rs")
s = p.read_text()

# rho_2 is deliberately undefined before G1: this probe only applies to the
# warranted shared Sort interface produced by G1.
required = """pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
}"""
if required not in s:
    raise SystemExit("V41_RHO2_NOT_DERIVABLE_BEFORE_G1")

import_anchor = "use InferFlag::*;\n"
assert import_anchor in s
s = s.replace(
    import_anchor,
    import_anchor + "use std::sync::atomic::{AtomicU64, Ordering};\n"
    + "pub static V41_G2_APP_PI: AtomicU64 = AtomicU64::new(0);\n"
    + "pub static V41_G2_APP_PI_PRE: AtomicU64 = AtomicU64::new(0);\n"
    + "pub static V41_G2_PROJ_IND: AtomicU64 = AtomicU64::new(0);\n"
    + "pub static V41_G2_PROJ_IND_PRE: AtomicU64 = AtomicU64::new(0);\n",
    1,
)

app_anchor = """        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
"""
if app_anchor not in s:
    raise SystemExit("V41_G2_APP_ANCHOR_MISSING")
app_repl = """        while let Some(arg) = args.pop() {
            V41_G2_APP_PI.fetch_add(1, Ordering::Relaxed);
            if matches!(fty, Value::Pi { .. }) {
                V41_G2_APP_PI_PRE.fetch_add(1, Ordering::Relaxed);
            }
            let fty_f = self.force_all(depth, fty);
"""
s = s.replace(app_anchor, app_repl, 1)

proj_anchor = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = self.force_all(depth, struct_ty);
"""
if proj_anchor not in s:
    raise SystemExit("V41_G2_PROJ_ANCHOR_MISSING")
proj_repl = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        V41_G2_PROJ_IND.fetch_add(1, Ordering::Relaxed);
        if matches!(struct_ty, Value::Rigid { head: RigidHead::Inductive(..), .. }) {
            V41_G2_PROJ_IND_PRE.fetch_add(1, Ordering::Relaxed);
        }
        let struct_ty_f = self.force_all(depth, struct_ty);
"""
s = s.replace(proj_anchor, proj_repl, 1)
p.write_text(s)

m = Path("src/main.rs")
ms = m.read_text()
use_anchor = "use sokonanoda::util::Config;\n"
assert use_anchor in ms
ms = ms.replace(
    use_anchor,
    use_anchor
    + "use sokonanoda::infer::{V41_G2_APP_PI, V41_G2_APP_PI_PRE, V41_G2_PROJ_IND, V41_G2_PROJ_IND_PRE};\n"
    + "use std::sync::atomic::Ordering;\n",
    1,
)
check_anchor = """    export_file.check_all_declars();
    // Pretty print as necessary
"""
assert check_anchor in ms
check_repl = """    export_file.check_all_declars();
    eprintln!(
        "MSI_V41_G2 app_pi={} app_pi_pre={} proj_ind={} proj_ind_pre={}",
        V41_G2_APP_PI.load(Ordering::Relaxed),
        V41_G2_APP_PI_PRE.load(Ordering::Relaxed),
        V41_G2_PROJ_IND.load(Ordering::Relaxed),
        V41_G2_PROJ_IND_PRE.load(Ordering::Relaxed),
    );
    // Pretty print as necessary
"""
ms = ms.replace(check_anchor, check_repl, 1)
m.write_text(ms)

print("V41_RHO2_POST_G1_PROBE_INSTALLED")
