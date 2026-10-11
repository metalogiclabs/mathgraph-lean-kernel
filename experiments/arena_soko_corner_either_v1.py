#!/usr/bin/env python3
"""Source-pinned Arena corner-case outcome parity gate for pinned baseline and two candidates.

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
# Tests the 18 official either-outcome corner cases, not correctness gold labels.
CASES={
"corner-cases/alg-conv-trans-acc-left":("a24e768f3f35871ce0915017d3f37416d85acebd7eea019b08ceafb4a3c6be1b",68991),
"corner-cases/alg-conv-trans-acc-right":("81ab1d26c3c760b243873d1432298bd135bbdc74259c69c7abca740c297c4fe2",69258),
"corner-cases/alg-conv-trans-acc":("5e368979269338849ce48b7591b218624ec072521ac4293930356b4fc55efb44",67968),
"corner-cases/alg-conv-trans-quot-left-def":("c14f073a6f062ee1a31bbc0e466eb2ffaced726393a423c8a68751f2cd2f49c1",10774),
"corner-cases/alg-conv-trans-quot-left":("9dd49f5ebd01c72f393f41fd718e9d40b371afe5e044446189b5765ac6dc0db5",8833),
"corner-cases/alg-conv-trans-quot-right":("53568a1d31b275e0255c18ea6c116a183909920b9d074c9cecab0a5b318d0a41",9254),
"corner-cases/alg-conv-trans-quot":("b95ab3f5f8c67411ca3bcb35c2888ce03d88bd651bb128a4e9da7f4304ad7db5",8680),
"corner-cases/eta-ctor":("03f9442400878003a0e2157373cdaf0ac20d680522cda534351ac5d25fb35001",9234),
"corner-cases/eta-rule-k":("abe59b1ceda4632c9964f46da1f9d485bf3ceb1045136fe8b32695369d33206b",6626),
"corner-cases/imax-right-successor":("00412ecd8a255812553a38f66bd84f521a233fce178742065005ff053c6cbd0f",806),
"corner-cases/let-value-type-mismatch":("52e75d78c948d466e90fb203e7a04192dde4273c7319d44fc261fd2b3b6beeac",601),
"corner-cases/positivity-whnf":("5e1c3ea262e5d57f0ffef2cbb7009a5a9020a977b648f109c0b0ab51ef3fa664",4808),
"corner-cases/nested-nonuniform-param":("396cea793fb200feb78db27bbc2168b3a10fcc84b67b64a26fc4df3f7ae834e0",9415),
"corner-cases/proj-maybe-prop-past":("69ad6bc0dd7e945c32076b8c39071ea4712b4f591dfa8c1d515b5dea96040f56",8313),
"corner-cases/proj-maybe-prop":("61dfee11e3ea0f8c88e812f735b4951b12067637c12b7a0c96bb4ef4003b3094",8308),
"corner-cases/proof-param-swap":("25cfb47d4c80ebe1ec61931898df8e6bd8d06793aebf3ee8b2a7cd00beca1abc",2961),
"corner-cases/subject-reduction-redex":("d056db183e4934cb5b0e838cdc20ee6ddb4a4a00a574423cd495e8b0e93bce53",68158),
"corner-cases/subject-reduction-reduct":("856836ce9c74591e0277047ad6448aadc2b93ef96eb9010e0922c32aacd055e2",67092),
}
bins={"baseline":"/tmp/soko-corner-baseline.bin",
      "sparse":"/tmp/soko-corner-sparse.bin",
      "compound":"/tmp/soko-corner-compound.bin"}
args=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
def file_hash(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        while chunk:=f.read(8*1024*1024):
            h.update(chunk)
    return h.hexdigest()
def save(rows):
    (out/"corner-either.json").write_text(json.dumps({
       "authority":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
       "stats_artifact":11506336524,"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
       "experiment":os.environ.get("GITHUB_SHA"),"rows":rows,
       "complete_corner_either_qualifier":len(rows)==len(CASES),
       "official_rank_qualified":False},indent=2,sort_keys=True)+"\n")
evidence=out/"corner-either.json"
rows=json.loads(evidence.read_text())["rows"] if evidence.is_file() else []
selection=[single] if single is not None else list(CASES)
assert all(name in CASES for name in selection),selection
for name in selection:
    assert name not in {r["case"] for r in rows},("DUPLICATE_CASE",name)
    expected_hash,expected_bytes=CASES[name]
    path=root/(name+".ndjson")
    assert path.is_file(),("MISSING_EXACT_EXPORT",name,path)
    assert path.stat().st_size==expected_bytes,("SIZE_MISMATCH",name,path.stat().st_size,expected_bytes)
    got=file_hash(path)
    assert got==expected_hash,("SHA_MISMATCH",name,got,expected_hash)
    row={"case":name,"bytes":expected_bytes,"sha256":got,"outcomes":{}}
    for arm,binary in bins.items():
        with path.open("rb") as f:
            start=time.monotonic()
            p=subprocess.run([binary,*args],stdin=f,stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE,timeout=3600)
            wall=time.monotonic()-start
        row["outcomes"][arm]={"exit":p.returncode,"wall_s":wall}
        assert p.returncode in (0,1),(name,arm,"MUST_RETURN_ACCEPT_OR_REJECT",p.returncode,p.stderr[-900:])
    assert len(set(x["exit"] for x in row["outcomes"].values()))==1,("DIVERGENT_CORNER",name,row)
    rows.append(row)
    save(rows)
    print("ARENA_PINNED_CORNER_EITHER="+json.dumps(row),flush=True)
    # Explicitly reclaim multi-gigabyte export space before next test.
    path.unlink()
assert len(rows)<=18
if len(rows)==18:
    print("ARENA_CORNER_EITHER_SUMMARY="+json.dumps({
      "passed":len(rows),"expected":18,
      "all_three_preserve_pinned_outcomes":True,"no_declines":True,
      "same_official_sha256":True,"official_rank_qualified":False}),flush=True)
else:
    print("ARENA_CORNER_EITHER_PROGRESS="+json.dumps({"passed":len(rows),"expected":18}),flush=True)
