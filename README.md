# About

This is an experimental fork on top of:
- [nanoda_lib](https://github.com/ammkrn/nanoda_lib)
- [sonanoda](https://github.com/datokrat/sonanoda)
- [still-nanoda](https://github.com/SchrodingerZhu/still-nanoda)

It is essentially a testing bed for high-performance typechecking for Lean.

You shouldn't use this for serious purposes.

Currently, it is about 9x faster than the official kernel, measured on mathlib.

Basically, the core conversion algorithm is entirely replaced by something closure-based. There are also some non-theoretical, purely programming optimisations.

## Structured result protocol

The existing invocation remains supported:

```text
sokonanoda CONFIG
```

Callers that need to distinguish a checked proof from a checker failure may opt
in to the closed `sokonanoda_result_v1` protocol:

```text
sokonanoda --result-file RESULT CONFIG
```

`RESULT` must not already exist. The checker writes the complete canonical JSON
record to a temporary file and publishes it atomically without replacing an
existing path. A consumer must require exactly one JSON object followed by one
line feed, reject unknown or missing fields, and check the exit/result pair:

| Exit | `outcome` | Allowed `reason_code` |
| ---: | --- | --- |
| 0 | `accepted` | `checked` |
| 1 | `rejected` | `duplicate_universe_parameters`, `theorem_type_not_prop`, or `declaration_type_mismatch` |
| 2 | `declined` | `unsupported_input` |
| 3 | `internal_failure` | `checker_error` |

Every record also has `"schema_version":1` and
`"protocol":"sokonanoda_result_v1"`. Missing, malformed, noncanonical, or
exit-mismatched records are not proof rejections. In particular, legacy exit 1
remains ambiguous and must fail closed.

The language-neutral schema and canonical byte vectors are in [`protocol/`](protocol/).

Only explicitly typed validation failures produce `rejected`. Ordinary Rust
panics, parser and configuration errors, I/O errors, and unexpected checker
failures produce `internal_failure`. When parallel checking sees both a typed
rejection and any unexpected panic, the internal failure takes precedence.
Structured mode also treats a `parse_only` configuration as an internal failure;
only a completed declaration check may produce `accepted`.
