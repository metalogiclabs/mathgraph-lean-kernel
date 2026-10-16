# Native identity observer audit

This audit covers the native identity accelerator, not an independent Lean
checker or a proof of the reuse dependency model. The Python
`engine.py::make_index` remains the differential oracle. A successful index is
not evidence that declarations have been type checked.

The independently written `test_native_identity.py` runs the real
`export-index CONFIG` process. Every supported success must equal the complete
Python index, including canonical encoded bytes, rather than selected digest
fields. The byte comparison also avoids Python equality conflating booleans
with numbers. The test file accepts `--indexer PATH`,
`MATHGRAPH_NATIVE_INDEXER`, or `target/release/export-index`; a missing binary is
an error rather than a skipped qualification.

## Representation and parser boundary

The implementation attaches an optional observer to the existing kernel parser.
Canonical fast rows use existing token parsing and emit identity events before
kernel metadata is discarded. General rows pass through the original typed
kernel parser and then through a strict JSON observer. Ordinary verification
constructs the parser without an observer. The identity path adds strict JSON
checks only when the observer is enabled.

The finalized kernel `Expr` and `Declar` structures cannot reconstruct the
Python identity. Required side information is retained by the observer:

| Information | Why reconstructing from the kernel loses identity |
| --- | --- |
| Lambda/Pi binder name and binderInfo | Both are omitted from `Expr` |
| Let binder name | Omitted; `nondep` itself is retained by the kernel |
| Original natVal decimal string | BigUint normalizes spelling such as `01` and `+1` |
| Definition, theorem and opaque `all` | The parser omits these lists from declarations |
| Quotient `kind` | Omitted when constructing `Declar::Quot` |
| Inductive `isReflexive` | Deserialized but discarded |
| Exact inductive `numNested` | Reduced to a Boolean in the kernel |
| Complete metadata JSON | Typed metadata skips unknown fields |
| Safety flags | Validated then omitted from declarations |
| Each original inductive row boundary | Flattening loses regrouping and empty rows |

The observer uses SHA-256 of Python's typed constructors, not kernel hash64,
pointer values, printed names, or normalized expressions/levels. Name component
kind and path remain distinct even when their display strings coincide.

The ordinary parser intentionally ignores missing and arbitrary binder
presentation metadata. Adding required binder fields to its serde schema would
change behavior. The observer instead requires the fields only for indexing.
The fast parser continues to read ignored binderInfo as bytes and decodes those
bytes only inside the identity branch. Existing ordinary-parser tests remain
the regression check for this boundary.

## Canonical bytes and dependency roots

Canonical strings match Python `ensure_ascii=True`: DEL and non-ASCII are
escaped, supplementary characters use UTF-16 surrogate pairs, hexadecimal is
lowercase, slash stays literal, and only backspace/tab/newline/form-feed/carriage
return use short control escapes. Object keys follow Unicode scalar order.
Metadata and arbitrary binderInfo retain supported nested JSON values.

The native SCC implementation was read against Python's two iterative
Kosaraju passes. Each root hashes sorted `(member name key, own digest)` pairs,
sorted roots of distinct outgoing components, and the sorted union of missing
dependency name keys. Components are hashed in dependency order. All members
receive their component root. Declaration names are removed from their own
direct dependency sets; universe parameters and binder names do not become
environment dependencies. Constructor names, recursor RHS expressions,
projection type names and declaration `all` lists do.

`complex` retains every original block start/size, including empty blocks, plus
ordered non-simple declaration identities. `schedule` retains declaration
order. Builtin pins scan all names, including undeclared names, and reject
ambiguous builtin displays.

## Unsupported and malformed input

Native errors return a nonzero exit and `{error, stage, declined}`. Identity
restrictions use `stage=identity`, `declined=true`; kernel parser errors use
`stage=kernel_parse`, with `declined` reflecting an actual kernel decline. No
error result contains a usable declaration index.

The supported native JSON numeric representation consists of i64/u64 integral
values. Floating point, negative zero spelling, oversized JSON integers,
non-finite values, and lone UTF-16 surrogates are never silently normalized.
Some are refused by the strict observer; some are rejected earlier by the real
kernel JSON parser. The adapter's explicit Python fallback preserves the
original Python indexer's unsupported-input classification, followed by the
existing full parser/selected-check guard. Fallback is not permission to accept
an input the original checker rejects.

Synthetic differential fixtures contain complete Lean/exporter metadata and
valid parser references, but may have incomplete or ill-typed declarations.
The suite separately demonstrates that Python can index an unused malformed
`bvar` string or minimal metadata while the real native parser rejects it.
Those cases test the distinction rather than weakening production parsing.

## Independent falsifiers and findings

The 30 test methods include eight seeded typed expression/declaration graphs,
each compared in compact, sparse-renumbered and shuffled general-parser forms.
Targeted cases cover all discarded metadata above; arbitrary nested binderInfo;
Unicode/control/astral strings; unknown and duplicate JSON keys at multiple
depths; raw control bytes; leading-zero JSON numbers; sparse/forward/duplicate
indices; cyclic roots with outgoing and missing dependencies; declaration
reordering; empty/regrouped blocks; absent builtin names and transitive builtin
helpers; unsafe/partial declarations; and exact metadata order/version rules.

The initial independent run found a real acceptance bug: fast strVal rows with
raw NUL, SOH, TAB, CR or US received successful indexes even though Python JSON
rejected them. The native parser was corrected to fall back for raw control
bytes only when the identity observer is active. The retained regression cases
now reject them. The audit also found that decoding ignored binderInfo as UTF-8
outside the observer would alter the ordinary parser; decoding was moved into
the identity branch. Unsupported numeric errors initially lost the explicit
decline classification; identity refusals now retain it in the protocol.

Validation command:

```sh
python3 experiments/incremental/test_native_identity.py -q
```

The local run passes all 30 methods. This is finite differential and
adversarial evidence. It does not prove general dependency extraction
completeness, certify all JSON inputs, establish mathematical equivalence of
expressions, or establish any performance result. Real workload/kernel-oracle
qualification is reported separately.
