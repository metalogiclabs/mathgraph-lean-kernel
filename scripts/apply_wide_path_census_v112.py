#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old,new,1)

p=Path("src/eval.rs")
c=p.read_text()
anchor="use std::collections::hash_map::Entry;\n"
insert=anchor+"""use std::sync::atomic::{AtomicU64, Ordering};

static V112_WIDE_KEY_CALLS: AtomicU64 = AtomicU64::new(0);
static V112_WIDE_PRUNE_CACHE_HITS: AtomicU64 = AtomicU64::new(0);
static V112_EXACT_CALLS: AtomicU64 = AtomicU64::new(0);
static V112_EXACT_CACHE_HITS: AtomicU64 = AtomicU64::new(0);
static V112_EXACT_BOUND_ABORTS: AtomicU64 = AtomicU64::new(0);
static V112_ROOT_SUCCESS: AtomicU64 = AtomicU64::new(0);
static V112_ROOT_FAIL: AtomicU64 = AtomicU64::new(0);
static V112_ROOT_WORDS_SUM: AtomicU64 = AtomicU64::new(0);
static V112_ROOT_WORDS_MAX: AtomicU64 = AtomicU64::new(0);
static V112_PRUNE_CALLS: AtomicU64 = AtomicU64::new(0);

pub fn report_wide_path_census_v112() {
    eprintln!(
        "V112_CENSUS wide_key_calls={} wide_prune_cache_hits={} exact_calls={} exact_cache_hits={} exact_bound_aborts={} root_success={} root_fail={} root_words_sum={} root_words_max={} prune_calls={}",
        V112_WIDE_KEY_CALLS.load(Ordering::Relaxed),
        V112_WIDE_PRUNE_CACHE_HITS.load(Ordering::Relaxed),
        V112_EXACT_CALLS.load(Ordering::Relaxed),
        V112_EXACT_CACHE_HITS.load(Ordering::Relaxed),
        V112_EXACT_BOUND_ABORTS.load(Ordering::Relaxed),
        V112_ROOT_SUCCESS.load(Ordering::Relaxed),
        V112_ROOT_FAIL.load(Ordering::Relaxed),
        V112_ROOT_WORDS_SUM.load(Ordering::Relaxed),
        V112_ROOT_WORDS_MAX.load(Ordering::Relaxed),
        V112_PRUNE_CALLS.load(Ordering::Relaxed),
    );
}
"""
c=replace_once(c,anchor,insert,"imports")

old="""    fn exact_wide_uses(&mut self, e: ExprPtr<'t>) -> Option<Vec<u64>> {
        if let Some(words) = self.tc_cache.wide_uses_cache.get(&e) {
            return Some(words.to_vec());
        }
        if usize::from(e.num_loose_bvars()) > 64 * MAX_WIDE_USE_WORDS {
            return None;
        }"""
new="""    fn exact_wide_uses(&mut self, e: ExprPtr<'t>) -> Option<Vec<u64>> {
        V112_EXACT_CALLS.fetch_add(1, Ordering::Relaxed);
        if let Some(words) = self.tc_cache.wide_uses_cache.get(&e) {
            V112_EXACT_CACHE_HITS.fetch_add(1, Ordering::Relaxed);
            return Some(words.to_vec());
        }
        if usize::from(e.num_loose_bvars()) > 64 * MAX_WIDE_USE_WORDS {
            V112_EXACT_BOUND_ABORTS.fetch_add(1, Ordering::Relaxed);
            return None;
        }"""
c=replace_once(c,old,new,"exact entry")

old="""    fn prune_env_wide(&mut self, e: E<'t>, words: &[u64]) -> E<'t> {
        if words.is_empty() {"""
new="""    fn prune_env_wide(&mut self, e: E<'t>, words: &[u64]) -> E<'t> {
        V112_PRUNE_CALLS.fetch_add(1, Ordering::Relaxed);
        if words.is_empty() {"""
c=replace_once(c,old,new,"prune entry")

old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
new="""        if k > 64 {
            V112_WIDE_KEY_CALLS.fetch_add(1, Ordering::Relaxed);
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                V112_WIDE_PRUNE_CACHE_HITS.fetch_add(1, Ordering::Relaxed);
                return *r;
            }
            let words = match self.exact_wide_uses(e) {
                Some(words) => {
                    V112_ROOT_SUCCESS.fetch_add(1, Ordering::Relaxed);
                    V112_ROOT_WORDS_SUM.fetch_add(words.len() as u64, Ordering::Relaxed);
                    V112_ROOT_WORDS_MAX.fetch_max(words.len() as u64, Ordering::Relaxed);
                    words
                }
                None => {
                    V112_ROOT_FAIL.fetch_add(1, Ordering::Relaxed);
                    return env;
                }
            };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
c=replace_once(c,old,new,"key env")
p.write_text(c)

p=Path("src/main.rs")
c=p.read_text()
old="    export_file.check_all_declars();\n"
new="""    export_file.check_all_declars();
    if std::env::var_os("MATHGRAPH_V112_CENSUS").is_some() {
        sokonanoda::eval::report_wide_path_census_v112();
    }
"""
c=replace_once(c,old,new,"main report")
p.write_text(c)
print("APPLY_WIDE_PATH_CENSUS_V112=PASS")
