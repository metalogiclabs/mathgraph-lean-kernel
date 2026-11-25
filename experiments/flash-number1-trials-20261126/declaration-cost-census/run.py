"""Complete-input diagnostic only. No decision is inferred from a timer."""
import importlib.util,json,os,re
from pathlib import Path

p=Path("experiments/flash-number1-trials-20261126")
spec=importlib.util.spec_from_file_location("bounded",p/"lambda-checking/native_mathlib.py")
bounded=importlib.util.module_from_spec(spec);spec.loader.exec_module(bounded)
root=Path(os.environ["RUNNER_TEMP"]);out=root/"declaration-cost-evidence"
protocol=json.loads((out/"protocol.json").read_text())
fixture=root/"lambda-input/mathlib.ndjson";binary=root/"declaration-cost.bin"
assert fixture.stat().st_size==protocol["full_input_bytes"]
assert bounded.digest(fixture)==protocol["full_input_sha256"]
assert re.search(r"test result: ok\. 46 passed; 0 failed",(out/"library-tests.log").read_text())
config=out/"config.json"
bounded.save(config,{"use_stdin":True,"num_threads":1,"parse_only":False,"nat_extension":True,
 "string_extension":True,"unsafe_permit_all_axioms":True,"unpermitted_axiom_hard_error":False,
 "print_success_message":True,"print_axioms":False})
identity={"input_sha256":protocol["full_input_sha256"],"binary_sha256":bounded.digest(binary),
 "src_tree":protocol["diagnostic_src_tree"],"boundary":protocol["boundary"]}
bounded.save(out/"identity.json",identity)
results=[]
for round_no in range(2):
 tag=f"round-{round_no}";stdout=out/(tag+".stdout");stderr=out/(tag+".stderr")
 row=bounded.run_bounded([str(binary),str(config)],fixture,stdout,stderr,600,11534336)
 row.update({"round":round_no,**identity})
 bounded.save(out/(tag+"-result.json"),row)
 assert row["raw_exit"]==0 and row["diagnostic_stop"] is None,row
 assert stdout.read_text().strip()=="Checked 739167 declarations with no errors"
 lines=[s.removeprefix("FLASH_DECLARATION_COSTS ") for s in stderr.read_text().splitlines()
  if s.startswith("FLASH_DECLARATION_COSTS ")]
 assert len(lines)==1
 census=json.loads(lines[0]);rows=census["rows"]
 assert census["declarations"]==739167 and len(rows)==739167
 assert {r[0] for r in rows}==set(range(739167))
 assert sum(r[1] for r in rows)==census["total_declaration_elapsed_ns"]
 bounded.save(out/(tag+"-census.json"),census)
 summary={k:v for k,v in census.items() if k!="rows"}
 bounded.save(out/(tag+"-summary.json"),summary)
 row["state"]="WARRANTED_BOUNDED_DIAGNOSTIC";results.append(row)
 bounded.save(out/"verification.json",{"state":"WARRANTED_BOUNDED_DIAGNOSTIC","results":results,
  "boundary":protocol["boundary"]})
 print(json.dumps({"round":round_no,"declarations":census["declarations"],
  "total_ns":census["total_declaration_elapsed_ns"],"top":census["top"][:10]}),flush=True)
