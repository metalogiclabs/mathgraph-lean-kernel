# Independent comparator review

No unsafe canonical equality was found at the actual receipt-index call site. The code replaces only the two full-index encodings used for equality. `authenticate_sparse_acceptance` is byte-for-byte unchanged at its AST source body, and still performs authentication, reconstruction, and the second reuse selection before this comparison. The comparison mode is added to signed provenance; default shared_json is intentional in this candidate and still requires exact-source qualification.

The actual helper handles exact type differences through the old encoder, always encodes float comparisons, falls back for non-ASCII string aliases, and falls back for whole dictionaries with any non-ASCII or non-exact-string key. Unsupported Python container kinds also use the encoder. ASCII-key dictionaries compare keysets and recursively compare values; lists preserve order. Shared exact dict/list identities are skipped only under the stated admitted, private, acyclic-tree precondition.

The independent script actually passed1604 canonical-reference cases, testing both argument directions (3208 comparator evaluations), including25 cases on each of eight real saved indexes. Both3436- and11653-declaration profiles include baseline, early-definition, unrelated-definition, and theorem-leaf; every canonical hash was matched to the downloaded candidate6e CI reference. Cases include shared/shallow/deep-copied/JSON-roundtripped structures; first/middle/last fingerprint changes; numerical type changes; signed zero and NaN; dependency/name/schedule changes; Unicode string/key aliases; tuple fallback;1400 generated cases; and nested depth128.

`observed-domain.json` independently records actual real-tree shapes: maximum nesting depth4; exact dict/list/str/int/None types; all object keys exact ASCII strings. Non-ASCII values occur219 times per original index and1499 per expanded index. Thus Unicode scalar fallback is relevant in the actual data, while arbitrary recursive Python object behavior is outside this schema.

A separate generic-depth probe records that depth500 distinct dictionary trees encode equally under the reference but the recursive comparator raises RecursionError. This is conservative failure outside the observed/native-index depth boundary, not false acceptance. The helper is not a general serializer replacement or validator; unsupported cyclic/shared arbitrary Python objects and skipped exception behavior remain outside its contract. No iterative generalization is needed for the measured index schema.

`summary.json` records tested source/comparator/helper hashes and every expected/actual result. The production file stayed byte-identical throughout the run. This is a correctness differential, not a speed measurement or independent new kernel qualification. No production, Git, or ROS edits were made.

Reproduce with supplied paths:

```sh
python differential.py --repo /path/retained-admission-worktree \
  --ci-zip /path/retained-kernel-admission-6e71704.zip \
  --original-index-root /path/original-qualification/references \
  --expanded-index-root /path/expanded-qualification/references \
  --out /path/fresh-comparator-review
```

The source worktree must contain the comparator revision recorded by this report. The script reads the unchanged6e authentication body from Git, imports only the candidate adapter, and executes no producer, checker, cache replay, or benchmark.
