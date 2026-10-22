# Independent authenticated-state cost arithmetic

`analyze_state.py` imports only Python's standard library. It reads the exact
three-arm benchmark summary, recomputes paired lifecycle wall/CPU economics and
the paired sums/means of each warm edit, and fails if published arithmetic differs.
It does not certify source semantics, HMACs, kernel verdicts or reuse decisions.

Actual CI publishes bounded provider ZIPs containing raw tar.xz parts. First use
the transport reconstruction helper to obtain the complete extracted directory;
do not point this reader at a ZIP containing only one tar part. Then run:

```sh
python3 analyze_state.py \
  --summary /extracted/artifacts/authenticated-state/summary.json \
  --evidence-root /extracted \
  --expected-source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 \
  --ci-run 39709067518 --out /fresh/output/analysis
```

`--summary` is an alias for `--local-summary`; the root must contain the supplied
summary. Runtime namespace paths resolve below the summary's own directory, so
the root may be the authenticated-state directory or an enclosing artifact root.
Historical absolute paths are not needed for this cost arithmetic.

For an already complete ZIP, `--artifact` remains supported. The ZIP must contain
exactly one `authenticated-state/summary.json`; select an exact path with
`--summary-member` if necessary (including a bare-root `summary.json`). No files
are extracted by the analyzer. Archive
and raw summary SHA256s, source identity, helper SHA256 and reported qualification
flags are recorded. Input bytes are rehashed before and after arithmetic/output.
ZIP path signatures are captured before opening; the held file descriptor and
current pathname must retain that identity. The preserved atomic-replacement
RED/GREEN case prevents old opened observations receiving a new artifact digest.
A decoded summary file is accepted with `--local-summary` instead; source-report
qualification remains an observed fact, not a new certificate from this helper.

The current development observation is explicitly unqualified:

```sh
python3 analyze_state.py \
  --local-summary /workspace/kernel-audit/authenticated-state/benchmark-stable-original-v3/summary.json \
  --expected-source b1931f8479a2bcd78af85ba79e60958963f89d96 \
  --out /fresh/output/smoke-analysis
```

Its one-pair/four-update, dirty-source input remains `CONTEXTUAL_SMOKE_ONLY`.
Markdown suppresses speedup promotion; signed positive/negative observations
remain in JSON. Source/CI is not silently replaced with the newer commit.

Outputs are `analysis.json`, a short `analysis.md`, and four CSVs containing raw
lifecycle arms, update wall/CPU phases/work counters, per-edit paired means and
per-process memory observations. Phase arithmetic uses exact JSON decimals;
published economics are independently reproduced using native-float summation,
ratio of arm medians, paired-index seeded bootstrap and the frozen confidence
endpoint rule. Lifecycle and warm economics use the original distinct seeds.

Startup, warm API sums, supported close and residual recording/sampling time are
separate. Cold history recovery is one observation/profile with warm OS caches;
state close is not separately recorded. Promotion is nested in persistence.
There is no isolated producer CPU measurement: before-consumer CPU combines
capture, producer and wrapper work, and signed clock-tick residuals remain.
State's inherited `materialization_and_hash` timing names delta-only recipe work.
State full-export zero counters are recorded; full-export scan/readback byte
totals are derived from export size and frozen source semantics. Direct input
preparation occurs outside its timer, favoring fresh Rust; producer cost remains
inside the candidate timer.

Logical runtime cache bytes restore `compressed_session_files` descriptors to
their `uncompressed_bytes` and add surviving small files. Archive transport
wrappers are excluded. Descriptors alone are a lower bound; namespace completeness
assumes supplied packaging includes every small runtime file. These are logical
persisted file contents, not filesystem allocation, compressed artifact storage,
native heap or aggregate RAM. No cache-space saving is presumed.
Summary input stability is verified; local runtime namespace contents are
observational file-size inputs whose immutable packaging is verified separately.

Candidate memory fields are per-process post-apply RSS and cumulative startup
VmHWM. Missing direct memory stays missing. No sum across process peaks, exact
per-input peak, aggregate peak or memory saving is inferred. Remaining native
index copies/loops, Python applicability scans, cold admission and history replay
prevent a change-proportional total-work claim.

Run `python3 -m unittest discover -v`. Portable synthetic tests need no project
imports. Real-smoke tests run only when the named preserved development fixture
exists; skips must not be reported as actual-fixture passes on a different host.
RED/GREEN logs and development CLI outputs are preserved alongside the helper.
