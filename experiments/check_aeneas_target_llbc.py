#!/usr/bin/env python3
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: check_aeneas_target_llbc.py <crate.llbc>")

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

t = data.get("translated", data)
targets = {"arg_is_ignorable", "result_is_not_proof"}
found = {}

for entry in t.get("item_names", []):
    if not isinstance(entry, dict):
        continue
    key = entry.get("key", {})
    if not isinstance(key, dict) or "Fun" not in key:
        continue
    parts = []
    for part in entry.get("value", []):
        ident = part.get("Ident") if isinstance(part, dict) else None
        if ident:
            parts.append(ident[0])
    for target in targets:
        if target in parts:
            found[target] = key["Fun"]

# Charon may use sparse/null slots in fun_decls. Null is not an error.
fun_decls = {
    decl.get("def_id"): decl
    for decl in t.get("fun_decls", [])
    if isinstance(decl, dict) and decl.get("def_id") is not None
}
print(f"fun_decl_count={len(fun_decls)}")

missing = set()
opaque = set()
wrong_source = set()
for target in sorted(targets):
    fun_id = found.get(target)
    if fun_id is None:
        print(f"{target}=MISSING")
        missing.add(target)
        continue
    decl = fun_decls.get(fun_id)
    if decl is None:
        print(f"{target}=DECL_MISSING_FOR_FUN_ID:{fun_id}")
        missing.add(target)
        continue

    meta = decl.get("item_meta") or {}
    span = (meta.get("span") or {}).get("data") or {}
    file_id = span.get("file_id")
    source_text = meta.get("source_text") or ""
    body = decl.get("body")

    # The target must be a real local production declaration with its Rust body.
    if body is None:
        print(f"{target}=FUN_ID:{fun_id}:OPAQUE")
        opaque.add(target)
        continue
    if target not in source_text:
        print(f"{target}=FUN_ID:{fun_id}:WRONG_SOURCE:file_id={file_id}")
        wrong_source.add(target)
        continue

    print(f"{target}=FUN_ID:{fun_id}:BODY:file_id={file_id}")

if missing:
    raise SystemExit(12)
if opaque:
    raise SystemExit(13)
if wrong_source:
    raise SystemExit(14)
