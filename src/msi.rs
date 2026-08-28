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

// --- Real-trace bridge -----------------------------------------------------
//
// The trace is deliberately observational. It does not affect checker control
// flow and it does not emit semantic names. Every inferred producer value is
// treated as an opaque state id, and two currently protected future probes are
// evaluated on it:
//
//   c0: the opaque outcome identity returned by the Sort-expecting future,
//       or 0 when that future cannot discharge directly;
//   c1: whether the application-function future can consume the value as an
//       already-established Pi-shaped interface.
//
// The offline compiler sees only (state, c0, c1).  The labels above are not in
// the emitted records.  This is the first bridge from real checker execution to
// the MSI equation E_B = intersection_c ker(c).

static TRACE_ENABLED: OnceLock<bool> = OnceLock::new();
static TRACE_COUNT: AtomicUsize = AtomicUsize::new(0);
const TRACE_LIMIT: usize = 250_000;

#[inline]
fn trace_enabled() -> bool {
    *TRACE_ENABLED.get_or_init(|| std::env::var_os("MSIKERNEL_TRACE").is_some())
}

/// Emit an anonymous, complete two-continuation observation vector for a real
/// inference result.  Pointer identity is used only as an opaque within-process
/// state identifier; it is never interpreted as semantic equality.
#[inline]
pub(crate) fn trace_producer(value: V<'_>) {
    if !trace_enabled() {
        return;
    }
    let n = TRACE_COUNT.fetch_add(1, Ordering::Relaxed);
    if n >= TRACE_LIMIT {
        return;
    }

    let state = value as *const Value<'_> as usize;
    let c0 = match value {
        // Reserve zero for the residual/no-direct-discharge outcome.
        Value::Sort { level, .. } => level.get_hash().wrapping_add(1),
        _ => 0,
    };
    let c1: u8 = if matches!(value, Value::Pi { .. }) { 1 } else { 0 };
    eprintln!("MSI_TRACE|{state:x}|{c0:x}|{c1}");
}
