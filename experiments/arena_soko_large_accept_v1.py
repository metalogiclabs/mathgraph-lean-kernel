#!/usr/bin/env python3
"""Source-pinned Arena omitted-positive acceptance gate for two candidate checkers.

The official October 2026 test-stats artifact 11506336524 fixes each export
name, size and SHA256. No test input is skipped on checker behavior, and
source qualification never relies on a leaderboard or test-name shortcut.
"""
import hashlib,json,os,pathlib,subprocess,sys,time

root=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
single=(sys.argv[4] if len(sys.argv)==5 and sys.argv[3]=='--single' else None)
assert len(sys.argv)==3 or (single is not None),sys.argv
# Official lean-kernel-arena@b83254de test-stats artifact #11506336524.
# Excludes already-qualified complete Mathlib and 125 small good cases.
CASES={
"cedar":("356d0db314cae2d913cee8c9447c10e08aa34f07946417b6a50e4d499506e031",872400300),
"con-leche":("b9ad1d958705760c6eb1c5cf3974ec0a4a3eb9dd765ff0648782fa49dee94a7f",551412545),
"cslib":("bc5c88e028d02a3c0789de6efb9cd96e8506d1e96b3d26672d28ae3bb33d0b30",2422584798),
"init":("620502ac9e63ba4a2dea9d46386c2f6aebc49faf8848ea3aaa18a77a09491a6a",347555345),
"navier-stokes-euler":("632943fca6795d48bc13e703aabfaef39931f9445f1275d2150a44f4de7b55e6",1559685706),
"perf/magma-string-n4":("158b54b527a3171cfff366e525d1f3ad78147f024e7946ec04fa6f20ef97bc5a",17353248),
"perf/magma-string-pair-n9":("deeeea5010e88e313dcf3d1b9642a5f9de8fb711066dd0256cec3b35d38c05ae",17354635),
"std":("289ed65a367abdc7388a855d2acf59cc1f401f5e06295acbb8a420682d9f00bd",596655086),
}
bins={"sparse":"/tmp/soko-large-sparse.bin",
      "compound":"/tmp/soko-large-compound.bin"}
args=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
def file_hash(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        while chunk:=f.read(8*1024*1024):
            h.update(chunk)
    return h.hexdigest()
def save(rows):
    (out/"large-positive.json").write_text(json.dumps({
       "authority":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
       "stats_artifact":11506336524,"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
       "experiment":os.environ.get("GITHUB_SHA"),"rows":rows,
       "complete_rebuilt_positive_qualifier":len(rows)==len(CASES),
       "official_rank_qualified":False},indent=2,sort_keys=True)+"\n")
evidence=out/"large-positive.json"
rows=json.loads(evidence.read_text())["rows"] if evidence.is_file() else []
selection=[single] if single is not None else list(CASES)
assert all(name in CASES for name in selection),selection
for name in selection:
    assert name not in {r["case"] for r in rows},("DUPLICATE_CASE",name)
    expected_hash,expected_bytes=CASES[name]
    path=root/(name+".ndjson")
    assert path.is_file(),("MISSING_EXACT_EXPORT",name,path)
    observed_bytes=path.stat().st_size
    got=file_hash(path)
    exact=(observed_bytes==expected_bytes and got==expected_hash)
    row={"case":name,"official_reference_bytes":expected_bytes,
         "official_reference_sha256":expected_hash,
         "rebuilt_bytes":observed_bytes,"rebuilt_sha256":got,
         "official_exact_input":exact,
         "evidence_class":"OFFICIAL_EXACT" if exact else "PINNED_REBUILT_DIFFERENT",
         "outcomes":{}}
    for arm,binary in bins.items():
        with path.open("rb") as f:
            start=time.monotonic()
            p=subprocess.run([binary,*args],stdin=f,stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE,timeout=3600)
            wall=time.monotonic()-start
        row["outcomes"][arm]={"exit":p.returncode,"wall_s":wall}
        assert p.returncode==0,(name,arm,"EXPECTED_ACCEPT",p.returncode,p.stderr[-900:])
    rows.append(row)
    save(rows)
    print("ARENA_PINNED_LARGE_POSITIVE="+json.dumps(row),flush=True)
    # Explicitly reclaim multi-gigabyte export space before next test.
    path.unlink()
assert len(rows)<=8
if len(rows)==8:
    print("ARENA_LARGE_POSITIVE_SUMMARY="+json.dumps({
      "passed":len(rows),"expected":8,
      "all_sparse_accept":True,"all_compound_accept":True,
      "official_exact_count":sum(r["official_exact_input"] for r in rows),
      "rebuilt_variant_count":sum(not r["official_exact_input"] for r in rows),
      "official_rank_qualified":False}),flush=True)
else:
    print("ARENA_LARGE_POSITIVE_PROGRESS="+json.dumps({"passed":len(rows),"expected":8}),flush=True)
