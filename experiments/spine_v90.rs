use crate::tests::util::test_ctx;
use crate::value::{self, Elim};
use std::error::Error;

#[test]
fn spine_v90_order_and_inline_boundary() -> Result<(), Box<dyn Error>> {
    test_ctx(None, |ctx| {
        let arena = bumpalo::Bump::new();
        let v = value::mk_sort(&arena, ctx.zero());
        let empty = value::spine_empty(&arena);
        for n in [0usize, 1, 7, 8, 9, 64, 65] {
            let mut spine = empty;
            for _ in 0..n {
                spine = value::spine_snoc(&arena, spine, Elim::app(v));
            }
            let materialized = spine.to_vec();
            assert_eq!(materialized.len(), n);
            assert_eq!(materialized.spilled(), n > 8);
            assert!(materialized.iter().all(|e| e.raw() == Elim::app(v).raw()));
            for i in 0..n {
                assert_eq!(materialized[i].raw(), spine.get(i).unwrap().raw());
            }
        }
    })
}

#[test]
fn spine_v90_mixed_eliminations_preserve_order() -> Result<(), Box<dyn Error>> {
    test_ctx(None, |ctx| {
        let arena = bumpalo::Bump::new();
        let v = value::mk_sort(&arena, ctx.zero());
        let name = ctx.str1(&"spine_v90");
        let mut spine = value::spine_empty(&arena);
        let expected = [Elim::app(v), Elim::proj(name, 0), Elim::app(v), Elim::proj(name, 7)];
        for e in expected {
            spine = value::spine_snoc(&arena, spine, e);
        }
        let materialized = spine.to_vec();
        assert!(!materialized.spilled());
        assert_eq!(materialized.iter().map(|e| e.raw()).collect::<Vec<_>>(), expected.iter().map(|e| e.raw()).collect::<Vec<_>>());
    })
}
