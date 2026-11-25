Update MathGraph to the reconciled core and its CLI, retaining exported-record correspondence checks and raw checker exit statuses. The newer core uses compact term/value identifiers and persists reconstructed inductive blocks.

This is an attributed integration of Jeremy Chen's Apache-2.0 [sokonanoda at 9a021b6](https://github.com/intgrah/sokonanoda/tree/9a021b66f804a1d1df68a981337c67413ef72f6b), with MathGraph validation and compatibility repairs. Copyright and licence notices are preserved. The description continues to identify the implementation's origin.

The pinned [source commit](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/bc704eebed4e009bc66af1a849f18315c11f1926) has source tree `06c257f0f2ff1f64711cfa54620b650e6dd59b7e`.

Validation:

- [Official Arena PR qualification](https://github.com/leanprover/lean-kernel-arena/actions/runs/45722992953) passed. All 231 prescribed outcomes run by that workflow were correct (92 rejects, 139 accepts). Of 30 additional non-scored corner cases, 28 returned a decision and two timed out. Results and input-stat archives were independently SHA-256 and CRC verified.
- 39 library tests; 230/230 exact portable prescribed outcomes; 16 additional source-correspondence controls.
- Complete unchanged Mathlib: all 739,167 declarations accepted in two alternating native rounds per arm.
- All nine additional complete large-input accepts, giving bounded evidence for 240/240 prescribed outcomes. The final [Navier–Stokes/Euler replay](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711718821/job/139547527336) accepted all 129,845 declarations with raw exit 0 and the exact prescribed input hash; its artifact archive was independently SHA-256 and CRC verified. Cedar's recovered recipe passed separately.

[Independently reverified execution evidence](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/795b4ba255675ca7147d4a23a12574a3c3b1d1b5/experiments/flash-number1-trials-20261126/continuation-reconciliation) includes exact input and executable hashes and preserves apparatus failures separately from checker verdicts. An additional malformed undeclared-universe control produces raw internal-error exit 3; it is not counted as semantic rejection.

Diagnostics on generic x86-64 builds showed 32.8% lower full-Mathlib native CPU and 24.9% lower peak RSS. A [calibrated full-input software diagnostic](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45712976230) counted 43.4% fewer application basic-block instructions. These have their recorded build and measurement boundaries; they are not Arena-native retired-instruction measurements or an official rank.

The official PR qualification passed. Its skip set differs from the separate 230-input portable qualification; these counts overlap and must not be added. The PR workflow skips Mathlib and several other large inputs. Full native-build Mathlib retired-instruction measurement and the public rank require the normal master workflow after integration, or an equivalent maintainer-run full workflow. PGO and speculative optimization prototypes are excluded from this source revision.
