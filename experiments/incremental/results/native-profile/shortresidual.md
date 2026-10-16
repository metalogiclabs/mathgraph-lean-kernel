# Residual serialization diagnostic

This is a pre-final diagnostic, not promotion evidence. The frozen engine and binaries were copied before the final all-bin release. Diagnostic wall medians were 0.4836 s early / 0.4483 s unrelated, versus 0.2895 / 0.2873 s for the captured raw full checker: deficits of 194 / 161 ms. These figures must not be mixed with the final qualification matrix or final executable pins.

| Captured component | SHA-256 |
|---|---|
| Engine | `650aa6f8eb49083ea867d30a85c3aedee1581b605cba7672e15ffc7fe6b1c4c2` |
| Native indexer, pre-final | `f1ef050679f559c7cb2c76548cc8dbb7290f01e7e99304d5e533247917f0262a` |
| Selected checker, pre-final | `869dbda8a8e2807c194b7937391cc659cfa437fc42bc365d51ec5c8f8cf2009d` |
| Raw full checker, pre-final | `37af7860da9da9425aef25b3a94825fe83ae26f23a013f2246a161e4cf9a40b8` |

The final announced native-indexer hash `daca81e13e52edfaa6dacaa7741565f49d1af109dc7ffa23aaea4a6e724137de` differs. The operation profile used isolated cache copies containing only newly checked baseline evidence; the same existing authority was used without regenerating or copying its key. All unprofiled, cProfile, and operation runs produced identical evidence IDs for each edit.

The following values are milliseconds from a separate operation run; canonical encoding calls each occurred once. cProfile independently measured approximately 52–53 ms in the JSON encoder. Instrumented child subprocess waiting is separate from Python CPU work.

| Operation | Early ms | Unrelated ms |
|---|---:|---:|
| Canonical prior payload for HMAC | 14.86 | 15.44 |
| Canonical new payload for HMAC | 13.48 | 14.64 |
| Canonical new signed envelope | 11.57 | 12.85 |
| Canonical final result output | 14.72 | 14.04 |
| Decode prior evidence JSON | 16.15 | 17.58 |
| Decode native index JSON | 27.09 | 26.51 |
| Write final result bytes | 0.59 | 0.64 |

The four substantive canonical encodings total 54.63 / 56.97 ms; the two large JSON decodes add 43.24 / 44.09 ms. These are operation measurements, not predicted end-to-end savings. The large native process and authenticated cache/persistence work remain after serialization.

A read-only microprobe reused the canonical payload bytes for both the HMAC and signed envelope. Fifteen repetitions per edit produced byte-identical 4,293,756-byte receipts, preserving their HMACs and evidence IDs. Median encoding cost fell from 28.21 to 16.25 ms early and 33.31 to 17.43 ms unrelated: only 11.96 / 15.88 ms saved. This candidate was not installed into the engine. The final 4.55–4.61 MB result alone still costs approximately 16.6–16.9 ms to encode in the separate microprobe.

The measured 12–16 ms byte-reuse opportunity is much smaller than the diagnostic 161–194 ms deficit. Serializer-only economics do not justify a production change as a route to beating raw full checking. Any final performance claim requires the final pinned qualification matrix; this diagnostic supports no promotion claim.

Per-call wall/CPU values, all repetitions, exact byte hashes, and parity results are in [residual-profile.json](residual-profile.json). Captured source, executable copies, the ad hoc profiling script, raw results, and `.prof` files remain outside git in `/workspace/kernel-audit/native-residual-profile/`. No issuer key was copied, printed, or regenerated.
