#!/usr/bin/env python3
"""Slice a Charon LLBC file to the dependency-closed production Sig island.

This does not rewrite Rust or synthesize semantics. It retains original Charon
objects/IDs and nulls unrelated declarations while preserving sparse indices.
"""
import copy
import json
import sys

TARGET_FUN_NAMES = {"arg_is_ignorable", "result_is_not_proof"}
HELPER_FUN_NAMES = {"ignorable"}
TARGET_TYPE_NAMES = {"Sig"}
TARGET_GLOBAL_NAMES = {"MAX_TRACKED"}

def last_ident(meta):
    for part in reversed((meta or {}).get("name", [])):
        if isinstance(part, dict) and "Ident" in part:
            return part["Ident"][0]
    return None

def local_relevance(meta):
    if not isinstance(meta, dict) or not meta.get("is_local"):
        return False
    return any(
        isinstance(part, dict)
        and part.get("Ident", [None])[0] == "relevance"
        for part in meta.get("name", [])
    )

def discover(t):
    keep = {"Fun": set(), "Type": set(), "Global": set(),
            "TraitDecl": set(), "TraitImpl": set()}

    for i, decl in enumerate(t.get("fun_decls", [])):
        if not isinstance(decl, dict):
            continue
        meta = decl.get("item_meta")
        name = last_ident(meta)
        if (
            name in TARGET_FUN_NAMES | HELPER_FUN_NAMES
            and local_relevance(meta)
            and name in (meta.get("source_text") or "")
            and decl.get("body") is not None
        ):
            keep["Fun"].add(i)

    for i, decl in enumerate(t.get("type_decls", [])):
        if not isinstance(decl, dict):
            continue
        meta = decl.get("item_meta")
        if last_ident(meta) in TARGET_TYPE_NAMES and local_relevance(meta):
            keep["Type"].add(i)

    for i, decl in enumerate(t.get("global_decls", [])):
        if not isinstance(decl, dict):
            continue
        meta = decl.get("item_meta")
        if last_ident(meta) in TARGET_GLOBAL_NAMES and local_relevance(meta):
            keep["Global"].add(i)

    return keep

def collect_refs(value, keep):
    if isinstance(value, dict):
        if set(value) == {"Fun"} and isinstance(value["Fun"], dict):
            fun = value["Fun"]
            if isinstance(fun.get("Regular"), int):
                keep["Fun"].add(fun["Regular"])
        if set(value) == {"Global"} and isinstance(value["Global"], dict):
            glob = value["Global"]
            if isinstance(glob.get("id"), int):
                keep["Global"].add(glob["id"])
        if set(value) == {"GlobalInitializer"} and isinstance(value["GlobalInitializer"], dict):
            glob = value["GlobalInitializer"]
            if isinstance(glob.get("id"), int):
                keep["Global"].add(glob["id"])
        for child in value.values():
            collect_refs(child, keep)
    elif isinstance(value, list):
        for child in value:
            collect_refs(child, keep)

def close_dependencies(t, keep):
    array_for = {
        "Fun": "fun_decls",
        "Global": "global_decls",
        "Type": "type_decls",
    }
    while True:
        before = {k: set(v) for k, v in keep.items()}
        for namespace, array_name in array_for.items():
            array = t.get(array_name, [])
            for idx in list(keep[namespace]):
                if 0 <= idx < len(array) and isinstance(array[idx], dict):
                    collect_refs(array[idx], keep)
        if all(before[k] == keep[k] for k in keep):
            return keep

def sparse(array, ids):
    return [value if i in ids else None for i, value in enumerate(array)]

def filter_names(entries, keep):
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not isinstance(key, dict) or len(key) != 1:
            continue
        namespace, idx = next(iter(key.items()))
        if namespace in keep and idx in keep[namespace]:
            out.append(entry)
    return out

def filter_ordered(entries, keep):
    out = []
    for entry in entries:
        if not isinstance(entry, dict) or len(entry) != 1:
            continue
        namespace, payload = next(iter(entry.items()))
        if namespace not in keep or not isinstance(payload, dict):
            continue
        if "NonRec" in payload and payload["NonRec"] in keep[namespace]:
            out.append(entry)
        elif "Rec" in payload:
            kept = [i for i in payload["Rec"] if i in keep[namespace]]
            if kept:
                out.append({namespace: {"Rec": kept}})
    return out

def assert_required(t, keep):
    required = {
        "Fun": TARGET_FUN_NAMES | HELPER_FUN_NAMES,
        "Type": TARGET_TYPE_NAMES,
        "Global": TARGET_GLOBAL_NAMES,
    }
    arrays = {
        "Fun": "fun_decls",
        "Type": "type_decls",
        "Global": "global_decls",
    }
    found = {}
    for namespace, names in required.items():
        actual = set()
        for idx in keep[namespace]:
            decl = t[arrays[namespace]][idx]
            if isinstance(decl, dict):
                actual.add(last_ident(decl.get("item_meta")))
        missing = names - actual
        if missing:
            raise SystemExit(f"missing required {namespace}: {sorted(missing)}")
        found[namespace] = sorted(actual)
    return found

def collect_hash_defs(value, defs):
    if isinstance(value, dict):
        if set(value) == {"HashConsedValue"}:
            payload = value["HashConsedValue"]
            if isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], int):
                defs.setdefault(payload[0], payload[1])
        for child in value.values():
            collect_hash_defs(child, defs)
    elif isinstance(value, list):
        for child in value:
            collect_hash_defs(child, defs)

def demote_hash_values(value):
    if isinstance(value, dict):
        if set(value) == {"HashConsedValue"}:
            payload = value["HashConsedValue"]
            if isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], int):
                value.clear()
                value["Deduplicated"] = payload[0]
                return
        for child in list(value.values()):
            demote_hash_values(child)
    elif isinstance(value, list):
        for child in value:
            demote_hash_values(child)

def rehydrate_hash_values(value, defs, defined, used):
    if isinstance(value, dict):
        if set(value) == {"Deduplicated"} and isinstance(value["Deduplicated"], int):
            idx = value["Deduplicated"]
            used.add(idx)
            if idx not in defined:
                if idx not in defs:
                    raise SystemExit(f"missing hash-cons definition {idx}")
                raw = copy.deepcopy(defs[idx])
                value.clear()
                value["HashConsedValue"] = [idx, raw]
                defined.add(idx)
                rehydrate_hash_values(raw, defs, defined, used)
            return
        if set(value) == {"HashConsedValue"}:
            idx, raw = value["HashConsedValue"]
            used.add(idx)
            defined.add(idx)
            rehydrate_hash_values(raw, defs, defined, used)
            return
        for child in value.values():
            rehydrate_hash_values(child, defs, defined, used)
    elif isinstance(value, list):
        for child in value:
            rehydrate_hash_values(child, defs, defined, used)

def main(src, dst, manifest_path):
    with open(src, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    hash_defs = {}
    collect_hash_defs(data, hash_defs)
    translated = data["translated"]

    keep = close_dependencies(translated, discover(translated))
    found = assert_required(translated, keep)

    translated["fun_decls"] = sparse(translated["fun_decls"], keep["Fun"])
    translated["type_decls"] = sparse(translated["type_decls"], keep["Type"])
    translated["global_decls"] = sparse(translated["global_decls"], keep["Global"])
    translated["trait_decls"] = sparse(translated["trait_decls"], keep["TraitDecl"])
    translated["trait_impls"] = sparse(translated["trait_impls"], keep["TraitImpl"])
    translated["ordered_decls"] = filter_ordered(translated["ordered_decls"], keep)
    translated["item_names"] = filter_names(translated["item_names"], keep)
    translated["short_names"] = filter_names(translated["short_names"], keep)
    translated["assoc_item_names"] = [None for _ in translated.get("assoc_item_names", [])]

    # Charon serializes hash-consed values by defining a key at its first
    # occurrence and using Deduplicated references thereafter. Pruning can
    # remove that first occurrence. Normalize then rehydrate only the keys
    # transitively required by this sliced semantic island.
    demote_hash_values(data)
    defined = set()
    used_hashcons = set()
    rehydrate_hash_values(data, hash_defs, defined, used_hashcons)

    with open(dst, "w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"))

    manifest = {
        "kept_ids": {k: sorted(v) for k, v in keep.items() if v},
        "required_names": found,
        "source": src,
        "output": dst,
        "hashcons_ids": sorted(used_hashcons),
        "hashcons_count": len(used_hashcons),
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print(json.dumps(manifest, sort_keys=True))

if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: slice_aeneas_target_llbc.py INPUT OUTPUT MANIFEST")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
