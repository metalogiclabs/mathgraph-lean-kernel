use crate::env::EnvLimit;
use crate::tc::TypeChecker;
use crate::util::{SessionCache, TcCache, PRUNE_DM_SHIFT};
use crate::value::{self, Env};

#[test]
fn prune_dm_v88_reuses_structural_result_across_declaration_reset() {
    super::util::test_export_file(None, |export| {
        export.with_ctx(|ctx, cache, arena| {
            let env = export.new_env(EnvLimit::Empty);
            let zero = ctx.zero();
            let sort = value::mk_sort(arena, zero);
            let base = value::env_empty(arena);
            let e = value::env_extend(arena, value::env_extend(arena, base, sort), sort);
            let var = ctx.mk_var(1);
            let mut tc = TypeChecker::new(ctx, &env, arena, None, cache);
            let first = tc.key_env(e, var);
            assert!(std::ptr::eq(first.lookup(1).unwrap(), sort));
            assert!(first.lookup(0).is_none());
            let mask = 2u64;
            let slot = (((e as *const Env<'_> as usize as u64).wrapping_mul(0x9E3779B97F4A7C15)
                ^ mask.wrapping_mul(0xD6E8FEB86659FD93)) >> PRUNE_DM_SHIFT) as usize;
            let ent = tc.tc_cache.prune_dm[slot];
            assert_eq!(ent.0, e as *const Env<'_> as usize);
            assert_eq!(ent.1, mask);
            assert!(std::ptr::eq(ent.2.unwrap(), first));
            tc.tc_cache.clear();
            let retained = tc.tc_cache.prune_dm[slot];
            assert!(std::ptr::eq(retained.2.unwrap(), first));
            // Bypass the per-environment one-entry memo to exercise the direct table.
            if let Env::Cons { prune, .. } = e { prune.set((0, None)); } else { unreachable!() }
            let second = tc.key_env(e, var);
            assert!(std::ptr::eq(first, second));
            tc.tc_cache.clear_session();
            assert!(tc.tc_cache.prune_dm.iter().all(|entry| entry.2.is_none()));
            // The same live arena remains usable after explicit invalidation.
            if let Env::Cons { prune, .. } = e { prune.set((0, None)); } else { unreachable!() }
            let third = tc.key_env(e, var);
            assert!(std::ptr::eq(third.lookup(1).unwrap(), sort));
            assert!(third.lookup(0).is_none());
        })
    }).unwrap();
}

#[test]
fn prune_dm_v88_session_boundary_invalidates_references() {
    let arena = bumpalo::Bump::new();
    let mut session = SessionCache::new(&arena);
    session.enter(|cache| {
        let e = cache.empty_env;
        cache.prune_dm[17] = (7, 3, Some(e));
        cache.clear();
        assert!(cache.prune_dm[17].2.is_some());
    });
    session.enter(|cache| {
        assert!(cache.prune_dm.iter().all(|entry| entry.2.is_none()));
        cache.prune_dm[23] = (9, 5, Some(cache.empty_env));
    });
    session.enter(|cache| {
        assert!(cache.prune_dm.iter().all(|entry| entry.2.is_none()));
    });
}

#[test]
fn prune_dm_v88_other_cache_invalidation_is_unchanged() {
    let arena = bumpalo::Bump::new();
    let mut cache = TcCache::new(&arena);
    cache.fvar_cache.insert(1, true);
    cache.ind_occ_cache.insert(2, false);
    cache.prune_dm[1] = (1, 1, Some(cache.empty_env));
    cache.clear();
    assert!(cache.fvar_cache.is_empty());
    assert!(cache.ind_occ_cache.is_empty());
    assert!(cache.prune_dm[1].2.is_some());
    cache.clear_session();
    assert!(cache.prune_dm.iter().all(|entry| entry.2.is_none()));
}
