from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()
needle = "use std::collections::hash_map::Entry;\n"
insert = """use std::collections::hash_map::Entry;\nuse std::collections::HashSet;\nuse std::sync::{Mutex, OnceLock};\nuse std::sync::atomic::{AtomicU64, Ordering};\n\nstatic KEY_ENV_SAMPLE_CALLS: AtomicU64 = AtomicU64::new(0);\nstatic KEY_ENV_SAMPLE_REPEATS: AtomicU64 = AtomicU64::new(0);\nstatic KEY_ENV_SAMPLE_SEEN: OnceLock<Mutex<HashSet<u128>>> = OnceLock::new();\n\n#[inline]\nfn note_key_env_pair(env_addr: usize, expr_addr: usize) {\n    let mut h = (env_addr as u64).wrapping_mul(0x9E3779B97F4A7C15);\n    h ^= (expr_addr as u64).wrapping_mul(0xD6E8FEB86659FD93);\n    h ^= h >> 33;\n    h = h.wrapping_mul(0xff51afd7ed558ccd);\n    h ^= h >> 33;\n    // Deterministic 1/1024 sample keeps the census cheap even on 100M+ calls.\n    if h & 1023 != 0 { return; }\n    KEY_ENV_SAMPLE_CALLS.fetch_add(1, Ordering::Relaxed);\n    let key = ((env_addr as u128) << 64) | expr_addr as u128;\n    let seen = KEY_ENV_SAMPLE_SEEN.get_or_init(|| Mutex::new(HashSet::new()));\n    let mut seen = seen.lock().unwrap();\n    if !seen.insert(key) {\n        KEY_ENV_SAMPLE_REPEATS.fetch_add(1, Ordering::Relaxed);\n    }\n}\n\npub fn report_key_env_repeat_census() {\n    let calls = KEY_ENV_SAMPLE_CALLS.load(Ordering::Relaxed);\n    let repeats = KEY_ENV_SAMPLE_REPEATS.load(Ordering::Relaxed);\n    let unique = calls.saturating_sub(repeats);\n    eprintln!(\"KEY_ENV_REPEAT_CENSUS sampled_calls={} sampled_repeats={} sampled_unique={}\", calls, repeats, unique);\n}\n"""
assert needle in s
s = s.replace(needle, insert, 1)
needle2 = """    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        let k = e.num_loose_bvars();\n"""
repl2 = """    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        note_key_env_pair(env as *const value::Env<'t> as usize, e.as_ref() as *const Expr<'t> as usize);\n        let k = e.num_loose_bvars();\n"""
assert needle2 in s
s = s.replace(needle2, repl2, 1)
p.write_text(s)

p = Path('src/main.rs')
s = p.read_text()
needle3 = """    export_file.check_all_declars();\n    // Pretty print as necessary\n"""
repl3 = """    export_file.check_all_declars();\n    sokonanoda::eval::report_key_env_repeat_census();\n    // Pretty print as necessary\n"""
assert needle3 in s
s = s.replace(needle3, repl3, 1)
p.write_text(s)
print('applied key_env repeat census v5')
