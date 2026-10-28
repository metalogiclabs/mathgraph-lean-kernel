//! Read-only follow-up to the exact-identity census: context and cost triage.
//! No result from this module is a license to reuse an evaluator value.

use crate::reuse_probe::MissClass;
use crate::expr::Expr;
use crate::util::ExprPtr;
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(usize)]
pub enum HeadKind {
    Var,
    Sort,
    Const,
    App,
    Pi,
    Lambda,
    Let,
    Proj,
    NatLit,
    StringLit,
}

const HEADS: [(&str, HeadKind); 10] = [
    ("Var", HeadKind::Var),
    ("Sort", HeadKind::Sort),
    ("Const", HeadKind::Const),
    ("App", HeadKind::App),
    ("Pi", HeadKind::Pi),
    ("Lambda", HeadKind::Lambda),
    ("Let", HeadKind::Let),
    ("Proj", HeadKind::Proj),
    ("NatLit", HeadKind::NatLit),
    ("StringLit", HeadKind::StringLit),
];

impl HeadKind {
    pub(crate) fn of_expr(e: &Expr<'_>) -> Self {
        match e {
            Expr::Var { .. } => Self::Var,
            Expr::Sort { .. } => Self::Sort,
            Expr::Const { .. } => Self::Const,
            Expr::App { .. } => Self::App,
            Expr::Pi { .. } => Self::Pi,
            Expr::Lambda { .. } => Self::Lambda,
            Expr::Let { .. } => Self::Let,
            Expr::Proj { .. } => Self::Proj,
            Expr::NatLit { .. } => Self::NatLit,
            Expr::StringLit { .. } => Self::StringLit,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Support {
    NoDirectReferences,
    MaxDirectIndex(u32),
    UnknownMissingDeclaration,
    UnknownTraversalCap,
    UnknownLocalChild,
}

impl Support {
    fn visible_before(self, cutoff: usize) -> Option<bool> {
        match self {
            Self::NoDirectReferences => Some(true),
            Self::MaxDirectIndex(index) => Some((index as usize) < cutoff),
            Self::UnknownMissingDeclaration | Self::UnknownTraversalCap | Self::UnknownLocalChild => None,
        }
    }
}

/// Conservative *direct syntactic* source support. It is not a closure
/// certificate: transitive definition bodies and temporary inductive contexts
/// still require independent verification before reuse.
pub(crate) fn direct_source_support(root: ExprPtr<'_>, max_nodes: usize) -> Support {
    let mut pending = vec![root];
    let mut visited = HashSet::new();
    let mut highest: Option<u32> = None;
    while let Some(e) = pending.pop() {
        if e.is_local() {
            return Support::UnknownLocalChild;
        }
        if !visited.insert(e) {
            continue;
        }
        if visited.len() > max_nodes {
            return Support::UnknownTraversalCap;
        }
        let mut include_name = |n: crate::util::NamePtr<'_>| -> Result<(), Support> {
            if n.is_local() {
                return Err(Support::UnknownLocalChild);
            }
            let idx = n.as_ref().decl_idx();
            if idx == crate::name::NO_DECL {
                return Err(Support::UnknownMissingDeclaration);
            }
            highest = Some(highest.map_or(idx, |old| old.max(idx)));
            Ok(())
        };
        match e.as_ref() {
            Expr::Const { name, .. } => {
                if let Err(reason) = include_name(*name) {
                    return reason;
                }
            }
            Expr::Proj { ty_name, structure, .. } => {
                if let Err(reason) = include_name(*ty_name) {
                    return reason;
                }
                pending.push(*structure);
            }
            Expr::App { fun, arg, .. } => {
                pending.push(*fun);
                pending.push(*arg);
            }
            Expr::Pi { binder_type, body, .. } | Expr::Lambda { binder_type, body, .. } => {
                pending.push(*binder_type);
                pending.push(*body);
            }
            Expr::Let { data, .. } => {
                pending.push(data.binder_type);
                pending.push(data.val);
                pending.push(data.body);
            }
            Expr::Var { .. } | Expr::Sort { .. } | Expr::NatLit { .. } | Expr::StringLit { .. } => {}
        }
    }
    highest.map_or(Support::NoDirectReferences, Support::MaxDirectIndex)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(usize)]
pub enum ScopeClass {
    First,
    SameGeneration,
    StrictSameCutoff,
    AdvancedVisibleDirectSupport,
    AdvancedBlockedDirectSupport,
    AdvancedUnknownSupport,
    RegressedPrefix,
    TemporaryContext,
    Excluded,
    UnmatchedSourceIdentity,
}

const CLASSES: [(&str, ScopeClass); 10] = [
    ("first", ScopeClass::First),
    ("same_generation", ScopeClass::SameGeneration),
    ("strict_same_cutoff", ScopeClass::StrictSameCutoff),
    ("advanced_visible_direct_support", ScopeClass::AdvancedVisibleDirectSupport),
    ("advanced_blocked_direct_support", ScopeClass::AdvancedBlockedDirectSupport),
    ("advanced_unknown_support", ScopeClass::AdvancedUnknownSupport),
    ("regressed_prefix", ScopeClass::RegressedPrefix),
    ("temporary_context", ScopeClass::TemporaryContext),
    ("excluded", ScopeClass::Excluded),
    ("unmatched_source_identity", ScopeClass::UnmatchedSourceIdentity),
];

#[derive(Debug, Clone, Copy)]
struct SourceContext {
    cutoff: usize,
    has_temporary_extension: bool,
    direct_support: Support,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct ScopeStats {
    counts: [u64; CLASSES.len()],
    recurrent_by_head: [u64; HEADS.len()],
    inclusive_elapsed_ns: [u64; CLASSES.len()],
    recurrent_elapsed_ns_by_head: [u64; HEADS.len()],
}

impl ScopeStats {
    fn merge(&mut self, other: &Self) {
        for i in 0..CLASSES.len() {
            self.counts[i] = self.counts[i].saturating_add(other.counts[i]);
            self.inclusive_elapsed_ns[i] = self.inclusive_elapsed_ns[i].saturating_add(other.inclusive_elapsed_ns[i]);
        }
        for i in 0..HEADS.len() {
            self.recurrent_by_head[i] = self.recurrent_by_head[i].saturating_add(other.recurrent_by_head[i]);
            self.recurrent_elapsed_ns_by_head[i] =
                self.recurrent_elapsed_ns_by_head[i].saturating_add(other.recurrent_elapsed_ns_by_head[i]);
        }
    }

    fn report(&self) -> serde_json::Value {
        let counts: serde_json::Map<String, serde_json::Value> = CLASSES
            .iter()
            .map(|&(name, class)| (name.into(), self.counts[class as usize].into()))
            .collect();
        let duration: serde_json::Map<String, serde_json::Value> = CLASSES
            .iter()
            .map(|&(name, class)| (name.into(), self.inclusive_elapsed_ns[class as usize].into()))
            .collect();
        let recurrent_by_head: serde_json::Map<String, serde_json::Value> = HEADS
            .iter()
            .map(|&(name, head)| (name.into(), self.recurrent_by_head[head as usize].into()))
            .collect();
        let recurrent_elapsed_ns_by_head: serde_json::Map<String, serde_json::Value> = HEADS
            .iter()
            .map(|&(name, head)| (name.into(), self.recurrent_elapsed_ns_by_head[head as usize].into()))
            .collect();
        serde_json::json!({
            "qualification": "CANDIDATE_CONTEXT_DIAGNOSTIC_ONLY",
            "sound_persistent_reuse_implemented": false,
            "speedup_measured": false,
            "source_support_limit_nodes": 8192,
            "scope_rule": "direct syntactic declaration references visible within both source prefixes; no temporary extension",
            "limitations": [
                "direct reference visibility does not prove transitive source dependency or a typed judgment",
                "source prefix and temporary environment are not a complete semantic certificate",
                "sampled inclusive elapsed nanoseconds are neither guest instructions nor causal savings",
                "nested sampled evaluations and OS scheduling may inflate inclusive times"
            ],
            "counts": counts,
            "recurrent_by_head": recurrent_by_head,
            "sampled_inclusive_elapsed_ns": duration,
            "recurrent_elapsed_ns_by_head": recurrent_elapsed_ns_by_head,
        })
    }
}

#[derive(Debug, Default)]
pub struct ScopeProbe {
    seen: HashMap<(u64, u64), SourceContext>,
    stats: ScopeStats,
}

impl ScopeProbe {
    pub fn observe(
        &mut self,
        source_epoch: u64,
        expr_identity: u64,
        miss: MissClass,
        cutoff: usize,
        has_temporary_extension: bool,
        head: HeadKind,
        support_once: impl FnOnce() -> Support,
    ) -> ScopeClass {
        let key = (source_epoch, expr_identity);
        let class = match miss {
            MissClass::Excluded => ScopeClass::Excluded,
            MissClass::SameGeneration => ScopeClass::SameGeneration,
            MissClass::First => {
                self.seen.insert(
                    key,
                    SourceContext { cutoff, has_temporary_extension, direct_support: support_once() },
                );
                ScopeClass::First
            }
            MissClass::AcrossGenerationCandidate => {
                if let Some(previous) = self.seen.get_mut(&key) {
                    let class = if has_temporary_extension || previous.has_temporary_extension {
                        ScopeClass::TemporaryContext
                    } else if cutoff == previous.cutoff {
                        ScopeClass::StrictSameCutoff
                    } else if cutoff < previous.cutoff {
                        ScopeClass::RegressedPrefix
                    } else {
                        match previous.direct_support.visible_before(previous.cutoff) {
                            Some(true) => ScopeClass::AdvancedVisibleDirectSupport,
                            Some(false) => ScopeClass::AdvancedBlockedDirectSupport,
                            None => ScopeClass::AdvancedUnknownSupport,
                        }
                    };
                    previous.cutoff = cutoff;
                    previous.has_temporary_extension = has_temporary_extension;
                    class
                } else {
                    ScopeClass::UnmatchedSourceIdentity
                }
            }
        };
        self.stats.counts[class as usize] += 1;
        if miss == MissClass::AcrossGenerationCandidate {
            self.stats.recurrent_by_head[head as usize] += 1;
        }
        class
    }

    pub fn record_inclusive_elapsed_ns(&mut self, class: ScopeClass, head: HeadKind, ns: u64) {
        let idx = class as usize;
        self.stats.inclusive_elapsed_ns[idx] = self.stats.inclusive_elapsed_ns[idx].saturating_add(ns);
        if !matches!(class, ScopeClass::First | ScopeClass::SameGeneration | ScopeClass::Excluded) {
            self.stats.recurrent_elapsed_ns_by_head[head as usize] =
                self.stats.recurrent_elapsed_ns_by_head[head as usize].saturating_add(ns);
        }
    }

    pub fn report(&self) -> serde_json::Value { self.stats.report() }
}

mod global_scope_report {
    use super::{ScopeProbe, ScopeStats};
    use std::sync::{Mutex, OnceLock};

    static REPORT: OnceLock<Mutex<ScopeStats>> = OnceLock::new();

    impl Drop for ScopeProbe {
        fn drop(&mut self) {
            let global = REPORT.get_or_init(|| Mutex::new(ScopeStats::default()));
            let mut guard = global.lock().expect("scope diagnostic aggregation lock poisoned");
            guard.merge(&self.stats);
        }
    }

    pub fn global_report() -> serde_json::Value {
        let global = REPORT.get_or_init(|| Mutex::new(ScopeStats::default()));
        global.lock().expect("scope diagnostic aggregation lock poisoned").report()
    }
}

pub use global_scope_report::global_report;

#[cfg(test)]
mod syntax_support_tests {
    use super::{direct_source_support, Support};
    use crate::expr::Expr;
    use crate::level::Level;
    use crate::name::{Name, NameNode};
    use crate::util::{ExprPtr, LevelPtr, LevelsPtr, NamePtr};

    #[test]
    fn shared_subexpression_counts_once_and_traversal_cap_forces_unknown() {
        let arena = bumpalo::Bump::new();
        let source_name = arena.alloc(NameNode::new(Name::Anon));
        source_name.set_decl_idx(37);
        let names = NamePtr::global(source_name);
        let levels = LevelsPtr::global(arena.alloc_slice_copy(&[] as &[LevelPtr<'_>]));
        let c = ExprPtr::global(arena.alloc(Expr::Const { hash: 0, name: names, levels }), 0);
        let app = ExprPtr::global(arena.alloc(Expr::App { hash: 0, fun: c, arg: c, fv_mask: 0 }), 0);
        assert_eq!(direct_source_support(app, 2), Support::MaxDirectIndex(37));
        assert_eq!(direct_source_support(app, 1), Support::UnknownTraversalCap);
    }

    #[test]
    fn missing_reference_index_and_projection_name_are_not_silently_assumed_visible() {
        let arena = bumpalo::Bump::new();
        let missing = NamePtr::global(arena.alloc(NameNode::new(Name::Anon)));
        let levels = LevelsPtr::global(arena.alloc_slice_copy(&[] as &[LevelPtr<'_>]));
        let c = ExprPtr::global(arena.alloc(Expr::Const { hash: 0, name: missing, levels }), 0);
        assert_eq!(direct_source_support(c, 8), Support::UnknownMissingDeclaration);

        let structure_name = arena.alloc(NameNode::new(Name::Anon));
        structure_name.set_decl_idx(8);
        let lvl = LevelPtr::global(arena.alloc(Level::Zero));
        let expr = ExprPtr::global(arena.alloc(Expr::Sort { hash: 0, level: lvl }), 0);
        let p = ExprPtr::global(
            arena.alloc(Expr::Proj { hash: 0, ty_name: NamePtr::global(structure_name), idx: 0, structure: expr, fv_mask: 0 }),
            0,
        );
        assert_eq!(direct_source_support(p, 8), Support::MaxDirectIndex(8));
        assert_eq!(direct_source_support(expr, 8), Support::NoDirectReferences);

        let locally_built = ExprPtr::local(arena.alloc(Expr::Const { hash: 0, name: missing, levels }));
        let mixed = ExprPtr::global(arena.alloc(Expr::App { hash: 0, fun: locally_built, arg: expr, fv_mask: 0 }), 0);
        assert_eq!(direct_source_support(mixed, 8), Support::UnknownLocalChild);
    }
}
