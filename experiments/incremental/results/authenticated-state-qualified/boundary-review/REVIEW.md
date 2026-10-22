# Read-only acceptance-boundary review

Source: `cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`.

No decisive unsound-acceptance path found in the inspected state representation, legacy hooks, or retained parser transition. This is a source review with seven fresh representation/authority unit tests; it is not a substitute for exact-source CI, actual kernel controls, or independent artifact replay. No runtime files were modified.

## Examined boundaries

- `authenticated_state.py:147`: state receipt CAS/HMAC/domain validation, parent-state binding, typed-index reconstruction and unchanged applicability predicate. The helper explicitly requires an authenticated parent.
- `authenticated_state.py:240`: every new prepare closes the old explicit-export descriptor and clears its path, proposed recipe, proposed state ID and attempted identity. A failure before staging has no candidate to export.
- `producer_delta.py:742`: transition parent/source/provenance and changed-byte digest checks precede index/parsing work. No empty-selected-list shortcut exists: the retained kernel request is unconditional. The expected selected/total count is checked before persistence.
- `src/bin/check_selected_retained_session.rs:98` and `src/parser.rs:819`: actual delta bytes are digest checked, parsed with `run_over(delta)` before selected checking, and append-only admitted DAG indices are guarded. Parser failure poisons the transition or terminates the process.
- `authenticated_state.py:280` and `revision_chain.py:222`: accepted receipts are issued only after actual selected kernel acceptance; source capture and signed head persistence precede accepted parent/recipe promotion. Failures poison all speculative processes.
- `authenticated_state.py:366`: current-state export refuses poisoned or pending sessions. Attempt export uses the staged candidate, carries `state_id=None`, and binds the parent state and exact delta. It cannot silently export the previously accepted snapshot as the rejected proposal.
- `revision_chain.py:48`: persisted sessions require an external expected head; cold history authenticates links and source captures, re-runs the source producer, checks exact regenerated delta digest, audits old objects before persistence, and genuinely rechecks selected obligations.

## Limits

The source issuer, process, key, native indexer/parser and serialization bridge remain trusted executable code; this review does not establish their complete formal correctness. The state ID identifies an authenticated construction, not a full-file SHA or semantic-equivalence theorem. Live private immutable bytes retain their prior admission despite subsequent disk corruption; cold storage corruption is refused. The expected head is an explicit latestness assumption. Initial admission, cold history replay, explicit full materialization and remaining whole-index/predicate traversals retain their stated costs.

At review time CI run `39709067518` remained in progress. No qualification or performance result is promoted here.
