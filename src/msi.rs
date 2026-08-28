//! Minimal Sufficient Interface runtime primitives.
//!
//! This module is intentionally small. It does not define a new universal
//! semantic ontology. It transports only facts that have already become true
//! at a producer boundary and that a downstream continuation can consume
//! without rediscovering them.

use crate::util::LevelPtr;
use crate::value::{Value, V};

/// The first compiled semantic interface.
///
/// `value` preserves the ordinary fallback path. `sort_level` is a certified
/// view exposed by the producer boundary when the inferred value is already a
/// raw `Sort`. Consumers may discharge a Sort-specific continuation directly;
/// otherwise they fall back to the existing generic checker.
#[derive(Debug, Clone, Copy)]
pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
}

impl<'a> InferCap<'a> {
    #[inline]
    pub(crate) fn from_value(value: V<'a>) -> Self {
        let sort_level = match value {
            Value::Sort { level, .. } => Some(*level),
            _ => None,
        };
        Self { value, sort_level }
    }
}

/// Exact continuation-local discharge for the first MSI capability.
///
/// This is deliberately equality-only: it does not claim that unequal level
/// pointers imply semantic inequality. Failure simply means "residual remains"
/// and the caller must use the ordinary conversion path.
#[inline]
pub(crate) fn same_sort_level<'a>(expected: V<'a>, actual: InferCap<'a>) -> bool {
    match (expected, actual.sort_level) {
        (Value::Sort { level, .. }, Some(actual_level)) => *level == actual_level,
        _ => false,
    }
}
