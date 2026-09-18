# QCKN V2 Lean Compounding Falsification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether the frozen QCKN compounding transition reduces selector-acquisition search on one held-out Lean Kernel Arena workload without weakening independent authority.

**Architecture:** A Python adapter uses the frozen RealityGraph capability, ledger, and CompiledPresent types to express acquisition, composition, promotion, retention, restart, and causal controls. A separate shell authority runner builds the selected Rust kernel and exact R1-disabled ablation, executes pinned Arena workloads, writes machine-readable evidence, and then invokes the adapter. The Python layer never manufactures performance evidence; the shell layer never changes QCKN search accounting.

**Tech Stack:** Python 3 standard library, frozen RealityGraph Python modules, Rust/Cargo, Bash, Nix, Valgrind Callgrind, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-qckn-v2-lean-compounding-falsification-design.md`

## Global Constraints

- RealityGraph baseline is `a78cb2b83ca792225df1b7cfe1a1f3b62a8f136c` on `qckn-v2-compounding-falsification-v1-frozen`.
- Arena is pinned to `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`.
- Selector portfolio is exactly `(0, 8, 32, 64)` and one inspected selector is one acquisition-search unit.
- Held-out workload is exactly `perf/magma-list-deep-n21`.
- Authority workloads are exactly `perf/beta-ladder`, `perf/magma-list-deep-n21`, `perf/grind-ring-5`, and `mathlib`.
- Performance gates are beta `>=2.0x`, held-out `>=1.01x`, grind `>=0.95x`, and Mathlib `>=0.999x` in Callgrind instructions.
- COLD, WARM, RAW_HISTORY, SHAM, and ANCESTOR_ABLATION use the same authority evidence.
- No official Arena repository change or pull request is permitted.

---

### Task 1: Pure QCKN Lean Adapter and Falsification Gates

**Files:**
- Create: `experiments/qckn_v2_lean_compounding.py`
- Create: `experiments/tests/test_qckn_v2_lean_compounding.py`
- Create: `experiments/tests/fixtures/passing-authority.json`

**Interfaces:**
- Consumes: `realitygraph.capability.FiniteCapability`, `compose_capabilities`; `CapabilityGraph`; `CompiledPresent`; `Ledger`; `MetaMemory`; a JSON authority mapping with exact per-workload status, parity, ablated instruction count, candidate instruction count, and speedup.
- Produces: `run_probe(authority: AuthorityEvidence) -> ProbeResult`, `load_authority(path: Path) -> AuthorityEvidence`, and canonical `ProbeResult.metrics() -> dict[str, object]`.

- [ ] **Step 1: Write the failing acquisition-control tests**

Add tests backed by `experiments/tests/fixtures/passing-authority.json`, whose four literal workload rows satisfy the frozen semantic and speedup gates. Assert:

```python
result = run_probe(PASSING_AUTHORITY)
assert result.arm("COLD").search_calls == 4
assert result.arm("WARM").search_calls == 0
assert result.arm("RAW_HISTORY").search_calls == 4
assert result.arm("SHAM").search_calls == 4
assert result.arm("ANCESTOR_ABLATION").search_calls == 4
assert result.arm("WARM").authority_checks == result.arm("COLD").authority_checks == 4
```

The production break caught is allowing uncompiled history, an untrusted matched-cost capability, or an ablated present to receive the warm shortcut.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH="$REALITYGRAPH_ROOT:$PWD" python -m unittest experiments.tests.test_qckn_v2_lean_compounding -v
```

Expected: import failure because `experiments.qckn_v2_lean_compounding` does not exist.

- [ ] **Step 3: Implement the minimal fixed portfolio and arm routing**

Create immutable `AuthorityEvidence`, `ArmMeasurement`, and `ProbeResult` dataclasses. Implement the exact portfolio `(0, 8, 32, 64)` with literal activation fractions from hosted atlas run `35327857819`. Select the first threshold retaining beta fraction `>=0.90` with Mathlib exposure `==0.0`. Only a restarted present containing capability id `lean-r1-depth64-standalone-v1`, the external-authority-derived certificate, frozen authority snapshot, and verifier id may return search cost zero.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: acquisition-control tests pass.

- [ ] **Step 5: Write the failing dependency and recertification tests**

Assert:

```python
assert set(result.dependent.dependencies) == {
    "lean-r1-context-projector-v1",
    "lean-depth64-selector-v1",
}
assert result.standalone.dependencies == ()
assert result.external_authority_passed
assert result.standalone.certificate_id.startswith("cert:lean-r1-depth64-authority-v1:")
```

Add a failing-authority fixture and assert it raises `CompoundingObstruction` with the exact gate code, preventing standalone identity creation.

- [ ] **Step 6: Verify RED, then implement composition and authority-gated standalone promotion**

Build a finite projector from raw context keys to R1 bucket keys and a finite selector from bucket keys to decisions. Use only `compose_capabilities` for the dependency-bearing composition. Validate external authority before minting the dependency-free standalone identity, then independently exhaustively attack that standalone finite decision table.

- [ ] **Step 7: Run focused tests and verify GREEN**

Expected: dependency and authority tests pass; a `1.009x` held-out fixture fails with `HELDOUT_COST_GATE_FAILED`.

- [ ] **Step 8: Write the failing retention, reserve, and restart tests**

Assert ACTIVE contracts `3 -> 1`, parents remain in provenance, main RESERVE is empty, the recovery control contains the selector, `require_removal` raises `RecoveryUnavailable`, compiled text/digest restart exactly, protected decision replay is unchanged, and restart with discovery disabled reproduces WARM.

- [ ] **Step 9: Verify RED, then implement ledger compilation and re-minimisation**

Append projector, selector, and standalone promotion events with causal parents. Compile only the standalone capability after replay and external authority checks. Retain explicit deletion evidence naming the replay digest and external certificate.

- [ ] **Step 10: Run the complete adapter tests and commit**

Run:

```bash
PYTHONPATH="$REALITYGRAPH_ROOT:$PWD" python -m unittest discover -s experiments/tests -p 'test_*.py' -v
python -m py_compile experiments/qckn_v2_lean_compounding.py experiments/tests/test_qckn_v2_lean_compounding.py
git diff --check
```

Commit:

```bash
git add experiments/qckn_v2_lean_compounding.py experiments/tests/test_qckn_v2_lean_compounding.py
git commit -m "test: encode Lean compounding falsification gates"
```

---

### Task 2: Real Lean Authority Runner

**Files:**
- Modify: `src/infer.rs`
- Create: `experiments/run_qckn_v2_lean_compounding.sh`

**Interfaces:**
- Consumes: current candidate commit, pinned Arena repository/commit, frozen RealityGraph checkout path, and the existing `R1_DIRECT_BETA_FUSION`/`r1_depth_split_allows` production path.
- Produces: `$ROOT/evidence/authority.json`, parity table, instruction measurements, provenance table, adapter result JSON, and exact obstruction text on RED.

- [ ] **Step 1: Write the failing Rust threshold-contract test**

Replace the private literal with:

```rust
pub(crate) const R1_MIN_DEPTH: u32 = 64;

#[inline]
pub(crate) fn r1_depth_split_allows(depth: u32) -> bool {
    depth >= R1_MIN_DEPTH
}
```

First update the existing test to assert `R1_MIN_DEPTH == 64`; run the branch's hosted-equivalent focused test command and confirm it fails because the constant does not exist.

- [ ] **Step 2: Implement the minimal named threshold and verify GREEN**

Run:

```bash
cargo test --locked qckn_depth_split_tests -- --nocapture
```

When Cargo is unavailable locally, record that exact toolchain obstruction and make this the first command in Actions before any benchmark.

- [ ] **Step 3: Write a shell preflight that fails before the runner exists**

The workflow test must call:

```bash
bash -n experiments/run_qckn_v2_lean_compounding.sh
```

Expected RED: file missing.

- [ ] **Step 4: Implement the authority runner**

The script must:

1. reject execution unless `GITHUB_SHA` and `REALITYGRAPH_ROOT` are set;
2. pin Arena to `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`;
3. build the candidate and an exact ablation created only by changing `R1_DIRECT_BETA_FUSION` from `true` to `false`;
4. build the four frozen Arena exports;
5. compare exit status and stdout exactly for both arms on every workload;
6. measure both arms once under deterministic Callgrind with the same PGO/toolchain configuration;
7. write literal counts and derived speedups to `authority.json`;
8. invoke the adapter with discovery disabled for WARM and write canonical `result.json`;
9. exit nonzero on the first named semantic or cost obstruction.

The runner must not enumerate alternate workloads or change thresholds after observing results.

- [ ] **Step 5: Verify shell syntax and adapter schema, then commit**

Run:

```bash
bash -n experiments/run_qckn_v2_lean_compounding.sh
PYTHONPATH="$REALITYGRAPH_ROOT:$PWD" python experiments/qckn_v2_lean_compounding.py --authority-json experiments/tests/fixtures/passing-authority.json --output /tmp/qckn-v2-lean-result.json
python -m json.tool /tmp/qckn-v2-lean-result.json >/dev/null
git diff --check
```

Commit:

```bash
git add src/infer.rs experiments/run_qckn_v2_lean_compounding.sh experiments/tests
git commit -m "feat: add Lean compounding authority runner"
```

---

### Task 3: Hosted Qualification Workflow

**Files:**
- Create: `.github/workflows/qckn-v2-lean-compounding-falsification-v1.yml`

**Interfaces:**
- Consumes: branch tip, frozen RealityGraph commit `a78cb2b83ca792225df1b7cfe1a1f3b62a8f136c`.
- Produces: one unit job and one real authority job, with `qckn-v2-lean-compounding-falsification-v1` evidence artifact.

- [ ] **Step 1: Add the workflow with a unit/preflight job**

The first job checks out this repository, installs Rust through the repository's Nix environment, checks out frozen RealityGraph in a sibling directory, runs Rust unit tests, runs Python adapter tests, verifies shell syntax, and fails before the expensive job on any RED.

- [ ] **Step 2: Add the real authority job**

The second job depends on unit/preflight, has a `360` minute timeout, checks out both repositories at exact commits, invokes the runner, and uploads the complete evidence directory even on failure.

- [ ] **Step 3: Validate workflow invariants**

Use a Python YAML text guard to assert the branch name, RealityGraph SHA, Arena SHA, `360` minute timeout, and artifact path occur exactly where expected. Do not add a third-party YAML dependency.

- [ ] **Step 4: Commit and publish the experimental branch**

Run `git diff --check`, commit, and push only `qckn-v2-lean-compounding-falsification-v1`. Do not open an official Arena PR and do not modify any champion/frozen branch.

---

### Task 4: Qualification, Evidence, and Exact Verdict

**Files:**
- Create: `docs/research/qckn-v2-lean-compounding-falsification-v1.md`
- Modify only if the first run reveals an implementation defect: adapter, runner, or workflow files covered by a new failing test.

**Interfaces:**
- Consumes: hosted run logs and artifact generated by Task 3.
- Produces: bounded GREEN or exact RED report with commit, run, artifact digest, frozen costs, all authority counts, ACTIVE/RESERVE/PROVENANCE state, controls, and obstruction if any.

- [ ] **Step 1: Monitor the first hosted run to completion**

Record branch tip, run id, job conclusions, durations, artifact name, size, and digest.

- [ ] **Step 2: Classify the result without metric substitution**

GREEN requires every spec gate. Otherwise report the first exact obstruction and retain all later available measurements as diagnostics only.

- [ ] **Step 3: Write the evidence report**

Include the full frozen comparison table, the authority table, ACTIVE `3 -> 1` result if promotion occurred, restart equality, reserve negative control, and the five-arm acquisition costs. State the narrow claim boundary verbatim from the spec.

- [ ] **Step 4: Run fresh verification**

Run the Python suite, Rust suite in the available Nix/Actions environment, shell syntax, canonical JSON generation, `git diff --check`, and confirm the worktree is clean after committing the evidence report.

- [ ] **Step 5: Freeze only a warranted GREEN milestone**

If and only if every gate is GREEN, create `qckn-v2-lean-compounding-falsification-v1-frozen` at the exact qualified tip. If RED, leave the experimental branch unfrozen and publish the named obstruction.
