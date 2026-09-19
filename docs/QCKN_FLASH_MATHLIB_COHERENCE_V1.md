# QCKN + Flash Mathlib Coherence V1

Status: active development frontier; no Arena PR.

## Target

Protected consequence:
- exact checker semantics;
- qualification ultimately requires current Arena 409-export parity.

Preference consequence:
- current Arena-style 4-thread PGO Mathlib wall time.

Development objective:
- drive qualified Mathlib wall below 60.0 s.

Frozen starting source:
- Flash 1 RC1 source: `a342c74f6eb913c25c6dae4138158023d1b9aa6a`.

Current reference evidence:
- Flash 1 RC1 qualified at 82.04 s median versus pinned Arena sokonanoda at 82.81 s on the same runner and pinned corpus.

The 60 s target requires an architectural-scale improvement, not merely accumulation of unrelated micro-wins.

## Canonical developmental stack

QCK:
- collapse distinctions only when they are warranted irrelevant to protected future consequence;
- preserve separators and UNKNOWN when authority is insufficient.

QCKN:
- observe;
- classify;
- intervene;
- verify;
- compile;
- restart/reuse.

RealityGraph:
- retain the current capability, residual, dependency, provenance, and authority ledger.

Flash:
- every verified event triggers dependency-driven reclosure of every affected Mathlib frontier;
- do not rerun unrelated searches;
- continue propagation until the affected graph reaches a local fixed point.

## Why whole-Mathlib profiling is insufficient

A single Mathlib wall time or Callgrind total loses three distinctions that matter to Arena wall:

1. declaration concentration;
2. four-thread critical-path / chunk imbalance;
3. which capabilities affect which residual families.

The checker currently distributes declaration work in fixed `CHUNK_SIZE=64` blocks across four worker threads. Therefore total work and Arena wall are not the same consequence.

## Active frontiers

### F1: scheduler geometry

Tournament:
- chunk 8;
- chunk 16;
- chunk 32;
- chunk 64;
- chunk 128.

Authority:
- same frozen semantics;
- native PGO;
- repeated Mathlib wall measurement;
- leader included in the same tournament.

Event types:
- `PREFERENCE_CHANGE` if another chunk geometry is faster;
- `DIST` if no meaningful wall effect is observed.

### F2: declaration heat graph

Profile the frozen RC1 checker in:
- production-like four-thread mode;
- serial mode.

Record:
- declaration index;
- declaration name hash;
- declaration kind;
- elapsed declaration cost;
- worker thread.

Derive:
- stable hot declarations;
- top-N cumulative cost;
- hot 64-declaration chunks;
- thread-load imbalance;
- declarations hot in both serial and parallel views;
- initial residual quotient classes.

### F3: structural residual attribution

Reuse and extend the already-earned R2/R3 structural counters:
- environment compression;
- conversion;
- forcing;
- inference cache;
- eval caches;
- closure application.

Next step after F2:
- snapshot counter deltas around only the hot residual representatives;
- avoid paying instrumentation overhead on the whole corpus once the hot set is known.

### F4: capability consequence matrix

For each retained capability `c` and residual class `R`, measure:

`M[R,c] = cost(R, active_present) - cost(R, active_present + c)`.

Initial retained capabilities include:
- direct Var evaluation;
- direct framed pruning;
- ordinary-Unfold neutral path;
- rigid-inductive neutral handling;
- app-HC preallocation;
- current sparse wide relevance;
- one-pass wide projection candidate;
- conversion/forcing interventions supported by residual evidence.

Do not globally activate a capability solely because it wins on one class.
If benefit is conditional, compile the minimum cheap selector that identifies its winning basin.

## Flash reclosure rule

When an event arrives:

1. add the warranted event to the current graph;
2. mark dependent residual classes, capabilities, selectors, scheduler states, and benchmark frontiers dirty;
3. recompute only the dirty dependency cone;
4. emit new equivalence / separator / obstruction / preference / promotion events;
5. repeat until the affected graph reaches a local fixed point;
6. compile the new present;
7. rerun full Mathlib only when a compounded candidate has earned authority.

This means, for example:
- a scheduler win changes which declarations are actually on the critical path;
- that reorders the hot residual set;
- that changes which capability experiment has highest expected value;
- a capability win can then remove a residual family;
- the residual atlas is immediately reclosed rather than reused stale.

## Fast funnel

Use expensive full-Mathlib runs only at the outer authority boundary.

Development funnel:

`full census -> residual quotient -> representative replay -> causal ablation -> selector/repair -> reclosure -> compounded candidate -> full PGO Mathlib -> 409 parity`.

Callgrind is a microscope, not the main iteration loop.

## Promotion gate

A candidate is promotable only if:
- semantic parity holds;
- the causal ablation supports the claimed capability;
- no protected broad-panel regression invalidates it;
- repeated Arena-style Mathlib wall improves the active champion;
- the result survives reclosure against the retained capability bank.

## Target interpretation

`<60 s` is a target, not a prediction.

From 82.04 s, reaching 60 s requires about a 1.37x speedup / 26.9% wall reduction.

If scheduler balance plus residual-local capability composition cannot account for most of that gap, the graph must emit an architectural obstruction and move to a larger representation change rather than continue harvesting sub-percent local patches.
