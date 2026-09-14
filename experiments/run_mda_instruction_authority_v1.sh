#!/usr/bin/env bash
set -euo pipefail
ROOT=/tmp/mda-instruction-authority-v1
rm -rf "$ROOT" && mkdir -p "$ROOT"

{
  echo "runner=$(uname -a)"
  echo "paranoid_before=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo missing)"
  perf --version || true
} | tee "$ROOT/system.txt"

set +e
perf stat -j -o "$ROOT/before.jsonl" -e duration_time -e task-clock -e instructions -- true
before_rc=$?
set -e
echo "before_rc=$before_rc" | tee -a "$ROOT/system.txt"

set +e
sudo sysctl -w kernel.perf_event_paranoid=-1 >"$ROOT/sysctl.txt" 2>&1
sysctl_rc=$?
set -e
echo "sysctl_rc=$sysctl_rc" | tee -a "$ROOT/system.txt"
cat "$ROOT/sysctl.txt" || true
echo "paranoid_after=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo missing)" | tee -a "$ROOT/system.txt"

set +e
perf stat -j -o "$ROOT/after.jsonl" -e duration_time -e task-clock -e instructions -- true
after_rc=$?
set -e
echo "after_rc=$after_rc" | tee -a "$ROOT/system.txt"

python3 - "$ROOT" <<'PY'
import json, pathlib, sys
r=pathlib.Path(sys.argv[1])
def parse(p):
    out={}
    if not p.exists(): return out
    for line in p.read_text(errors="replace").splitlines():
        try: d=json.loads(line)
        except: continue
        if "event" in d and "counter-value" in d:
            ev=d["event"].split(":")[0]
            try: out[ev]=float(d["counter-value"])
            except: pass
    return out
data={"before":parse(r/"before.jsonl"),"after":parse(r/"after.jsonl")}
data["hardware_instruction_authority_available"]=data["after"].get("instructions",0)>0
(r/"authority.json").write_text(json.dumps(data,indent=2)+"\n")
print("MDA_INSTRUCTION_AUTHORITY="+("PASS" if data["hardware_instruction_authority_available"] else "UNAVAILABLE"))
print(json.dumps(data,sort_keys=True))
PY
