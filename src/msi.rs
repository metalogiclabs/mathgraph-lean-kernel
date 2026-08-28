//! Minimal Sufficient Interface runtime primitives.
//!
//! This module is intentionally small. It does not define a new universal
//! semantic ontology. It transports only facts that have already become true
//! at a producer boundary and that a downstream continuation can consume
//! without rediscovering them.

use crate::util::LevelPtr;
use crate::value::{Value, V};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy)]
pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
}

impl<'a> InferCap<'a> {
    #[inline]
    pub(crate) fn from_value(value: V<'a>) -> Self {
        trace_producer(value);
        let sort_level = match value {
            Value::Sort { level, .. } => Some(*level),
            _ => None,
        };
        Self { value, sort_level }
    }
}

#[inline]
pub(crate) fn same_sort_level<'a>(expected: V<'a>, actual: InferCap<'a>) -> bool {
    match (expected, actual.sort_level) {
        (Value::Sort { level, .. }, Some(actual_level)) => *level == actual_level,
        _ => false,
    }
}

// Real-trace bridge. The emitted record contains no semantic names: only an
// opaque event id and the outcomes of two protected future observations. This
// is observational only and cannot change checker control flow.
static TRACE_ENABLED: OnceLock<bool> = OnceLock::new();
static TRACE_COUNT: AtomicUsize = AtomicUsize::new(0);
const TRACE_LIMIT: usize = 250_000;

#[inline]
fn trace_enabled() -> bool {
    *TRACE_ENABLED.get_or_init(|| std::env::var_os("MSIKERNEL_TRACE").is_some())
}

#[inline]
pub(crate) fn trace_producer(value: V<'_>) {
    if !trace_enabled() {
        return;
    }
    let n = TRACE_COUNT.fetch_add(1, Ordering::Relaxed);
    if n >= TRACE_LIMIT {
        return;
    }

    // c0 is the opaque outcome of the first future observation. Zero means the
    // future cannot discharge directly. Nonzero values are opaque outcome ids.
    let c0 = match value {
        Value::Sort { level, .. } => level.get_hash().wrapping_add(1),
        _ => 0,
    };
    // c1 is the outcome of the second future observation.
    let c1: u8 = if matches!(value, Value::Pi { .. }) { 1 } else { 0 };
    eprintln!("MSI_TRACE|{n:x}|{c0:x}|{c1}");
}
