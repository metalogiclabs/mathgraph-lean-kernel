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

fun_decls = {decl.get("def_id"): decl for decl in t.get("fun_decls", [])}
print(f"fun_decl_count={len(fun_decls)}")

missing = set()
opaque = set()
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
    body = decl.get("body")
    if body is None:
        print(f"{target}=FUN_ID:{fun_id}:OPAQUE")
        opaque.add(target)
    else:
        print(f"{target}=FUN_ID:{fun_id}:BODY")

if missing:
    raise SystemExit(12)
if opaque:
    raise SystemExit(13)
