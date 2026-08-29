from pathlib import Path

p = Path('src/infer.rs')
s = p.read_text()

# This probe is deliberately compatible with the V37/V39 native SHARED Sort
# interface. It measures only unresolved downstream Pi and Inductive demand.
import_anchor = "use crate::value::{self, Closure, RigidHead, Value, C, E, V};\n"
assert import_anchor in s
s = s.replace(import_anchor, import_anchor + "use std::sync::atomic::{AtomicU64, Ordering};\n", 1)

scope_anchor = """#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CheckScope<'a> {
"""
assert scope_anchor in s
counters = """pub static V39_APP_PI: AtomicU64 = AtomicU64::new(0);
pub static V39_APP_PI_PRE: AtomicU64 = AtomicU64::new(0);
pub static V39_PROJ_IND: AtomicU64 = AtomicU64::new(0);
pub static V39_PROJ_IND_PRE: AtomicU64 = AtomicU64::new(0);

"""
s = s.replace(scope_anchor, counters + scope_anchor, 1)

app_anchor = """        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
"""
assert app_anchor in s
app_repl = """        while let Some(arg) = args.pop() {
            V39_APP_PI.fetch_add(1, Ordering::Relaxed);
            if matches!(fty, Value::Pi { .. }) {
                V39_APP_PI_PRE.fetch_add(1, Ordering::Relaxed);
            }
            let fty_f = self.force_all(depth, fty);
"""
s = s.replace(app_anchor, app_repl, 1)

proj_anchor = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = self.force_all(depth, struct_ty);
"""
assert proj_anchor in s
proj_repl = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        V39_PROJ_IND.fetch_add(1, Ordering::Relaxed);
        if matches!(struct_ty, Value::Rigid { head: RigidHead::Inductive(..), .. }) {
            V39_PROJ_IND_PRE.fetch_add(1, Ordering::Relaxed);
        }
        let struct_ty_f = self.force_all(depth, struct_ty);
"""
s = s.replace(proj_anchor, proj_repl, 1)
p.write_text(s)

m = Path('src/main.rs')
ms = m.read_text()
use_anchor = "use sokonanoda::util::Config;\n"
assert use_anchor in ms
ms = ms.replace(use_anchor, use_anchor + "use sokonanoda::infer::{V39_APP_PI, V39_APP_PI_PRE, V39_PROJ_IND, V39_PROJ_IND_PRE};\nuse std::sync::atomic::Ordering;\n", 1)
check_anchor = """    export_file.check_all_declars();
    // Pretty print as necessary
"""
assert check_anchor in ms
check_repl = """    export_file.check_all_declars();
    eprintln!(
        "MSI_V39_POST app_pi={} app_pi_pre={} proj_ind={} proj_ind_pre={}",
        V39_APP_PI.load(Ordering::Relaxed),
        V39_APP_PI_PRE.load(Ordering::Relaxed),
        V39_PROJ_IND.load(Ordering::Relaxed),
        V39_PROJ_IND_PRE.load(Ordering::Relaxed),
    );
    // Pretty print as necessary
"""
ms = ms.replace(check_anchor, check_repl, 1)
m.write_text(ms)

print('applied native post-Sort residual probe v39')
