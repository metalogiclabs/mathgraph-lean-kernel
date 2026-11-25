//! Cost and context controls for repeated evaluation in Flash's existing cache.
use super::util::test_export_file;
use crate::{env::EnvLimit, value::{self, Value}};
use std::{cell::Cell, error::Error, ptr};

thread_local! {
    static ENVIRONMENT_PROJECTIONS: Cell<usize> = const { Cell::new(0) };
}

pub(crate) fn record_environment_projection() {
    ENVIRONMENT_PROJECTIONS.with(|n| n.set(n.get() + 1));
}

fn projections() -> usize {
    ENVIRONMENT_PROJECTIONS.with(Cell::get)
}

// Removing the early lookup must cause a second environment projection here.
// This counts executed work rather than asserting a particular cache layout.
#[test]
fn repeated_open_evaluation_avoids_environment_reprojection() -> Result<(), Box<dyn Error>> {
    test_export_file(None, |export| export.with_tc(EnvLimit::Empty, |tc| {
        let prop = tc.ctx.prop();
        let outer = tc.ctx.mk_var(1);
        let expression = tc.ctx.mk_lambda(prop, outer);
        let captured = value::mk_sort(tc.arena, tc.ctx.zero());
        let environment = tc.env_extend(tc.empty_env(), captured);
        let first = tc.eval(1, environment, expression);
        let before = projections();
        let second = tc.eval(1, environment, expression);
        assert!(ptr::eq(first, second));
        assert_eq!(projections(), before, "repeated evaluation projected its environment again");
    }))
}

// Aliasing an expression without its original environment would conflate x and y.
#[test]
fn early_evaluation_keeps_distinct_captured_values() -> Result<(), Box<dyn Error>> {
    test_export_file(None, |export| export.with_tc(EnvLimit::Empty, |tc| {
        let zero = tc.ctx.zero();
        let one = tc.ctx.succ(zero);
        let prop = tc.ctx.prop();
        let outer = tc.ctx.mk_var(1);
        let expression = tc.ctx.mk_lambda(prop, outer);
        let x = value::mk_sort(tc.arena, zero);
        let y = value::mk_sort(tc.arena, one);
        let ex = tc.env_extend(tc.empty_env(), x);
        let ey = tc.env_extend(tc.empty_env(), y);
        for (environment, expected_level) in [(ex, zero), (ey, one), (ex, zero), (ey, one)] {
            let closure = tc.eval(1, environment, expression);
            let result = tc.apply(1, closure, x);
            assert!(matches!(result, Value::Sort { level, .. } if *level == expected_level));
        }
    }))
}

// The same closed syntax under u := 0 and u := 1 must have different domains.
#[test]
fn early_evaluation_keeps_universe_substitutions() -> Result<(), Box<dyn Error>> {
    test_export_file(None, |export| export.with_tc(EnvLimit::Empty, |tc| {
        let zero = tc.ctx.zero();
        let one = tc.ctx.succ(zero);
        let name = tc.ctx.str1("early_cache_universe");
        let parameter = tc.ctx.param(name);
        let sort = tc.ctx.mk_sort(parameter);
        let expression = tc.ctx.mk_pi(sort, sort);
        let parameters = tc.ctx.alloc_levels_slice(&[parameter]);
        for expected_level in [zero, one, zero, one] {
            let substitution = tc.ctx.alloc_levels_slice(&[expected_level]);
            let result = tc.eval_inst(expression, parameters, substitution);
            match result {
                Value::Pi { domain: Value::Sort { level, .. }, .. } => assert_eq!(*level, expected_level),
                _ => panic!("expected a Pi with a universe-instantiated domain"),
            }
        }
    }))
}

// Session invalidation must discard the shortcut together with the original cache.
#[test]
fn early_evaluation_is_invalidated_with_existing_cache() -> Result<(), Box<dyn Error>> {
    test_export_file(None, |export| export.with_tc(EnvLimit::Empty, |tc| {
        let prop = tc.ctx.prop();
        let outer = tc.ctx.mk_var(1);
        let expression = tc.ctx.mk_lambda(prop, outer);
        let captured = value::mk_sort(tc.arena, tc.ctx.zero());
        let environment = tc.env_extend(tc.empty_env(), captured);
        tc.eval(1, environment, expression);
        tc.tc_cache.clear();
        let before = projections();
        tc.eval(1, environment, expression);
        assert!(projections() > before, "clear retained an evaluation result");
        tc.tc_cache.clear_session();
        let before = projections();
        tc.eval(1, environment, expression);
        assert!(projections() > before, "session reset retained an evaluation result");
    }))
}
