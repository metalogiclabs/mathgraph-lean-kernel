#!/usr/bin/env python3
"""Experimental source-pinned joint type/value cache for Flash VNext.

Hypothesis: open expression evaluation and type inference should address one
contextual judgment record, retaining independent validity for the checked type
and for an evaluated value. The two current maps use precisely the same source
contextual key: (Id(key_env(env, e)), e), but make separate lookup/insert trips.

Safety design:
- type checked_under is unchanged; unchecked evaluation cannot authorize Check;
- no proof, conversion, universe, axiom or reduction rule changes;
- only OPEN composite eval uses unified cache; CLOSED eval retains exact original
  expression + universe-substitution caches;
- re-read record after recursive computation to preserve entries created inside;
- source-pinned, strict asserts, fail-closed on a shifted upstream revision.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: flash_vnext_judgment_cache_patch.py CHECKER_TREE")
root=Path(sys.argv[1])
infer=root/"src/checker/infer.rs"
cache=root/"src/checker/cache.rs"
evalfile=root/"src/checker/eval.rs"

def one(text,old,new,label):
    count=text.count(old)
    assert count == 1, f"{label}: expected 1 exact site, got {count}"
    return text.replace(old,new)

s=infer.read_text()
s=one(s,
    """pub(crate) struct CachedType<'a> {
    pub(crate) result: V<'a>,
    pub(crate) checked_under: CheckScope<'a>,
}
""",
    """pub(crate) struct CachedType<'a> {
    pub(crate) result: V<'a>,
    pub(crate) checked_under: CheckScope<'a>,
}

/// One contextual expression key, but deliberately separate authorities.
/// A value from eval() does NOT certify that the type is checked.
#[derive(Debug, Clone, Copy)]
pub(crate) struct CachedJudgment<'a> {
    pub(crate) checked_type: Option<CachedType<'a>>,
    pub(crate) value: Option<V<'a>>,
}
""",
    "typed contextual record")
s=one(s,
    """        if let Some(cached) = self.tc_cache.type_cache.get(&key)
            && (flag == InferOnly || cached.checked_under == scope)
        {
            return cached.result;
        }""",
    """        if let Some(judgment) = self.tc_cache.judgment_cache.get(&key)
            && let Some(cached) = judgment.checked_type
            && (flag == InferOnly || cached.checked_under == scope)
        {
            return cached.result;
        }""",
    "type lookup")
s=one(s,
    """        self.tc_cache.type_cache.insert(
            key,
            CachedType {
                result: r,
                checked_under,
            },
        );""",
    """        // Recursive checking or evaluation may have filled the value.
        // Do not overwrite that evidence when the checked type is published.
        let value = self.tc_cache.judgment_cache.get(&key).and_then(|j| j.value);
        self.tc_cache.judgment_cache.insert(
            key,
            CachedJudgment {
                checked_type: Some(CachedType {
                    result: r,
                    checked_under,
                }),
                value,
            },
        );""",
    "typed result publication")
infer.write_text(s)

s=cache.read_text()
s=one(s,"use crate::checker::infer::CachedType;",
      "use crate::checker::infer::CachedJudgment;","cache import")
s=one(s,
    """        #[cap(SESSION)] open_eval_cache: PtrMap<(Id<'a, Env<'a>>, ExprPtr<'t>), V<'a>>,""",
    """        #[cap(SESSION)] judgment_cache: PtrMap<(Id<'a, Env<'a>>, ExprPtr<'t>), CachedJudgment<'a>>,""",
    "open cache")
s=one(s,
    """        #[cap(SESSION)] type_cache: PtrMap<(Id<'a, Env<'a>>, ExprPtr<'t>), CachedType<'a>>,""",
    """""",
    "type cache")
cache.write_text(s)

s=evalfile.read_text()
s=one(s,"use crate::checker::cache::{hashcons, memo};",
      "use crate::checker::cache::{hashcons, memo};\nuse crate::checker::infer::CachedJudgment;","eval import")
s=one(s,
    """            return memo!(
                self.tc_cache.open_eval_cache,
                (Id::of(te), e),
                self.eval_no_cache(depth, te, e)
            );""",
    """            let key = (Id::of(te), e);
            if let Some(judgment) = self.tc_cache.judgment_cache.get(&key)
                && let Some(value) = judgment.value
            {
                return value;
            }
            let value = self.eval_no_cache(depth, te, e);
            // This same record may have been populated by nested inference.
            // Preserve the checked-type receipt without conferring authority
            // on any result merely because it was evaluated.
            let checked_type = self.tc_cache.judgment_cache
                .get(&key).and_then(|j| j.checked_type);
            self.tc_cache.judgment_cache.insert(
                key,
                CachedJudgment { checked_type, value: Some(value) },
            );
            return value;""",
    "open evaluation cache")
evalfile.write_text(s)
print("FLASH_VNEXT_JUDGMENT_CACHE=APPLIED_DISTINCT_CHECKED_AND_VALUE_AUTHORITY",flush=True)
