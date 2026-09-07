use crate::env::EnvLimit;
use crate::tc::TypeChecker;
use crate::util::{SessionCache, TcCache};
use crate::value::{self, Value};

#[test]
fn fvar_reuse_v87_retains_only_structural_memo() {
    super::util::test_export_file(None, |export| {
        export.with_ctx(|ctx, cache, arena| {
            let env = export.new_env(EnvLimit::Empty);
            let zero = ctx.zero();
            let sort = value::mk_sort(arena, zero);
            let mut tc = TypeChecker::new(ctx, &env, arena, None, cache);
            let bvar = tc.mk_bvar_hc(0, sort);
            let sort_key = sort as *const Value<'_> as usize;
            let bvar_key = bvar as *const Value<'_> as usize;
            assert!(!tc.value_has_free_bvar(0, sort));
            assert!(tc.value_has_free_bvar(0, bvar));
            assert_eq!(tc.tc_cache.fvar_cache.get(&sort_key), Some(&false));
            assert_eq!(tc.tc_cache.fvar_cache.get(&bvar_key), Some(&true));
            tc.tc_cache.ind_occ_cache.insert(17, true);
            tc.tc_cache.prune_dm[0] = (1, 2, Some(tc.empty_env()));
            tc.tc_cache.clear();
            assert_eq!(tc.tc_cache.fvar_cache.get(&sort_key), Some(&false));
            assert_eq!(tc.tc_cache.fvar_cache.get(&bvar_key), Some(&true));
            assert!(tc.tc_cache.ind_occ_cache.is_empty());
            assert_eq!(tc.tc_cache.prune_dm[0].0, 0);
            assert_eq!(tc.tc_cache.prune_dm[0].1, 0);
            assert!(tc.tc_cache.prune_dm[0].2.is_none());
            assert!(!tc.value_has_free_bvar(0, sort));
            assert!(tc.value_has_free_bvar(0, bvar));
            tc.tc_cache.fvar_cache.clear();
            assert!(!tc.value_has_free_bvar(0, sort));
            assert!(tc.value_has_free_bvar(0, bvar));
        })
    }).unwrap();
}

#[test]
fn fvar_reuse_v87_session_reset_is_fail_closed() {
    let arena = bumpalo::Bump::new();
    let mut session = SessionCache::new(&arena);
    session.enter(|cache| {
        cache.fvar_cache.insert(7, true);
        cache.ind_occ_cache.insert(8, true);
    });
    session.enter(|cache| {
        assert!(cache.fvar_cache.is_empty());
        assert!(cache.ind_occ_cache.is_empty());
        cache.fvar_cache.insert(9, false);
    });
    session.enter(|cache| {
        assert!(cache.fvar_cache.is_empty());
    });
}

#[test]
fn fvar_reuse_v87_clear_session_preserves_no_stale_entries() {
    let arena = bumpalo::Bump::new();
    let mut cache = TcCache::new(&arena);
    cache.fvar_cache.insert(1, true);
    cache.clear();
    assert_eq!(cache.fvar_cache.get(&1), Some(&true));
    cache.clear_session();
    assert!(cache.fvar_cache.is_empty());
}
