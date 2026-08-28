from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()

old_import = '''use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n'''
new_import = '''use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\nuse std::collections::BTreeMap;\nuse std::sync::{Mutex, OnceLock};\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n'''
assert old_import in s, 'import anchor not found'
s = s.replace(old_import, new_import, 1)

anchor = '''fn rigid_head_eq<'a>(hx: RigidHead<'a>, hy: RigidHead<'a>) -> bool {\n'''
instrument = r'''static MSI_CT_TOTAL: AtomicU64 = AtomicU64::new(0);
static MSI_CT_SAME_SORT: AtomicU64 = AtomicU64::new(0);
static MSI_CT_CALLERS: OnceLock<Mutex<BTreeMap<(&'static str, u32), u64>>> = OnceLock::new();

#[inline(never)]
fn msi_ct_origin<'a>(file: &'static str, line: u32, a: &Value<'a>, b: &Value<'a>) {
    let total = MSI_CT_TOTAL.fetch_add(1, Relaxed) + 1;
    if let (Value::Sort { level: lx, .. }, Value::Sort { level: ly, .. }) = (a, b) {
        if lx == ly {
            let same = MSI_CT_SAME_SORT.fetch_add(1, Relaxed) + 1;
            let callers = MSI_CT_CALLERS.get_or_init(|| Mutex::new(BTreeMap::new()));
            let mut callers = callers.lock().unwrap();
            *callers.entry((file, line)).or_insert(0) += 1;
            if same % 100_000 == 0 {
                eprintln!("MSI_CT_ORIGIN total={} same_sort={} callers={:?}", total, same, &*callers);
            }
        }
    }
}

'''
assert anchor in s, 'rigid anchor not found'
s = s.replace(anchor, instrument + anchor, 1)

old = '''    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {\n        self.unbudgeted(|s| s.unify::<true>(depth, a, b))\n    }\n'''
new = '''    #[track_caller]\n    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {\n        let loc = std::panic::Location::caller();\n        msi_ct_origin(loc.file(), loc.line(), a, b);\n        self.unbudgeted(|s| s.unify::<true>(depth, a, b))\n    }\n'''
assert old in s, 'conv_types_at anchor not found'
s = s.replace(old, new, 1)

p.write_text(s)
print('applied MSI v30 conv_types caller provenance census')
