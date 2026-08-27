from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()

anchor = 'use std::collections::hash_map::Entry;\n'
insert = r'''use std::collections::{HashSet, hash_map::Entry};
use std::sync::{Mutex, OnceLock};
use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Default)]
struct BqClass {
    keys: HashSet<(u64, usize, u64)>,
    vals: HashSet<(u64, usize)>,
    pairs: HashSet<(u64, usize, u64, usize)>,
}

#[derive(Default)]
struct BqState {
    all: BqClass,
    classes: [BqClass; 5],
}

static BQ_STATE: OnceLock<Mutex<BqState>> = OnceLock::new();
static BQ_EPOCH: AtomicU64 = AtomicU64::new(0);

pub fn advance_behavioural_quotient_epoch() {
    BQ_EPOCH.fetch_add(1, Ordering::Relaxed);
}

#[inline]
fn bq_class(e: ExprPtr<'_>) -> usize {
    match e.as_ref() {
        Expr::App { .. } => 0,
        Expr::Proj { .. } => 1,
        Expr::Let { .. } => 2,
        Expr::Pi { .. } => 3,
        Expr::Lambda { .. } => 4,
        _ => unreachable!(),
    }
}

#[inline]
fn bq_record<'t>(env: E<'t>, e: ExprPtr<'t>, v: V<'t>) {
    let ep = e.get_hash();
    let envp = env as *const value::Env<'t> as usize;
    let mix = (envp as u64).wrapping_mul(0x9E3779B97F4A7C15) ^ ep.wrapping_mul(0xD6E8FEB86659FD93);
    if mix & 1023 != 0 { return; }
    let epoch = BQ_EPOCH.load(Ordering::Relaxed);
    let vp = v as *const Value<'t> as usize;
    let c = bq_class(e);
    let st = BQ_STATE.get_or_init(|| Mutex::new(BqState::default()));
    let mut st = st.lock().unwrap();
    st.all.keys.insert((epoch, envp, ep));
    st.all.vals.insert((epoch, vp));
    st.all.pairs.insert((epoch, envp, ep, vp));
    st.classes[c].keys.insert((epoch, envp, ep));
    st.classes[c].vals.insert((epoch, vp));
    st.classes[c].pairs.insert((epoch, envp, ep, vp));
}

pub fn print_behavioural_quotient_census() {
    let Some(st) = BQ_STATE.get() else {
        eprintln!("MSI_BQ_CENSUS {{\"sampled_keys\":0}}");
        return;
    };
    let st = st.lock().unwrap();
    fn row(c: &BqClass) -> String {
        let k = c.keys.len();
        let v = c.vals.len();
        let collapse = if k == 0 { 1.0 } else { v as f64 / k as f64 };
        format!("{{\\\"keys\\\":{},\\\"values\\\":{},\\\"pairs\\\":{},\\\"value_per_key\\\":{:.9},\\\"compression_x\\\":{:.6}}}",
            k, v, c.pairs.len(), collapse, if v == 0 { 1.0 } else { k as f64 / v as f64 })
    }
    eprintln!("MSI_BQ_CENSUS {{\\\"sample_rate\\\":1024,\\\"epochs\\\":{},\\\"all\\\":{},\\\"app\\\":{},\\\"proj\\\":{},\\\"let\\\":{},\\\"pi\\\":{},\\\"lambda\\\":{}}}",
        BQ_EPOCH.load(Ordering::Relaxed) + 1,
        row(&st.all), row(&st.classes[0]), row(&st.classes[1]), row(&st.classes[2]), row(&st.classes[3]), row(&st.classes[4]));
}
'''
if anchor not in s:
    raise SystemExit('eval import anchor missing')
s = s.replace(anchor, insert, 1)

old = '''            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;\n            }\n            let v = self.eval_no_cache(depth, te, e);\n            self.tc_cache.open_eval_cache.insert(key, v);\n            return v;\n'''
new = '''            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                bq_record(te, e, v);\n                return v;\n            }\n            let v = self.eval_no_cache(depth, te, e);\n            self.tc_cache.open_eval_cache.insert(key, v);\n            bq_record(te, e, v);\n            return v;\n'''
if old not in s:
    raise SystemExit('open eval anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)

p = Path('src/tc.rs')
s = p.read_text()
old = '            sbump.reset();\n            tctx.expr_cache.shrink();\n'
new = '            crate::eval::advance_behavioural_quotient_epoch();\n            sbump.reset();\n            tctx.expr_cache.shrink();\n'
if old not in s:
    raise SystemExit('session reset anchor missing')
p.write_text(s.replace(old, new, 1))

p = Path('src/main.rs')
s = p.read_text()
old = '    export_file.check_all_declars();\n'
new = '    export_file.check_all_declars();\n    sokonanoda::eval::print_behavioural_quotient_census();\n'
if old not in s:
    raise SystemExit('main anchor missing')
p.write_text(s.replace(old, new, 1))
print('applied MSI behavioural quotient census v9 epoch fix')
