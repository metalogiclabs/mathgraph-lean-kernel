#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v87-benchmark
mkdir -p "$ROOT/out" "$ROOT/control" "$ROOT/candidate"
# The caller must first verify the successful, frozen v87 preflight.
git fetch --quiet --depth=1 origin "$BASE"
git archive "$BASE" | tar -x -C "$ROOT/control"
cp -a "$ROOT/control/." "$ROOT/candidate/"
python3 experiments/patch_fvar_reuse_v87.py "$ROOT/candidate" | tee "$ROOT/out/patch.log"
diff -u "$ROOT/control/src/util.rs" "$ROOT/candidate/src/util.rs" > "$ROOT/out/candidate.patch" || test "$?" -eq 1
export RUSTFLAGS='-C target-cpu=native'
export CARGO_TARGET_DIR="$ROOT/target-control"
(cd "$ROOT/control" && cargo build --release --locked -q) |& tee "$ROOT/out/control-build.log"
cp "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/control-checker"
export CARGO_TARGET_DIR="$ROOT/target-candidate"
(cd "$ROOT/candidate" && cargo build --release --locked -q) |& tee "$ROOT/out/candidate-build.log"
cp "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/checker"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
test "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
cd "$ROOT"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import subprocess,sys,hashlib,json,time,statistics,math
r=Path(sys.argv[1]); out=r/'out'; cfg=r/'config.json'
results={'base':'08ddb26718c86213262943ca19ae8cf1b03fa922','arena':'91f376e4baacf2df0c478e7173bccb2a6adac5c5','build':'native-no-pgo','status':'IN_PROGRESS','corpora':{}}
def save():
    (out/'results.json').write_text(json.dumps(results,indent=2))
def run(binary, data, suffix):
    start=time.perf_counter()
    p=subprocess.run([str(binary),str(cfg)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200)
    elapsed=time.perf_counter()-start
    (out/f'{suffix}.stdout').write_bytes(p.stdout)
    (out/f'{suffix}.stderr').write_bytes(p.stderr)
    return {'rc':p.returncode,'seconds':elapsed,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
try:
    for corpus in ('std','cedar','mathlib'):
        data=(r/'arena'/'_build'/'tests'/f'{corpus}.ndjson').read_bytes()
        assert data, corpus
        entry={'input_sha256':hashlib.sha256(data).hexdigest(),'runs':[]}
        results['corpora'][corpus]=entry
        save()
        reference=run(r/'control-checker',data,f'{corpus}.reference')
        candidate=run(r/'checker',data,f'{corpus}.candidate')
        entry['reference']=reference; entry['candidate']=candidate
        save()
        assert reference['rc']==candidate['rc']==0,(corpus,reference,candidate)
        assert reference['stdout_sha256']==candidate['stdout_sha256'],corpus
        assert reference['stderr_sha256']==candidate['stderr_sha256'],corpus
        entry['exact_replay']='PASS'
        print(f'V87_{corpus.upper()}_EXACT_REPLAY=PASS',flush=True)
        for i in range(5):
            order=['control','candidate'] if i%2==0 else ['candidate','control']
            for arm in order:
                binary=r/('control-checker' if arm=='control' else 'checker')
                result=run(binary,data,f'{corpus}.{arm}.{i}')
                entry['runs'].append({'pass':i,'arm':arm,**result})
                save()
                assert result['rc']==0,(corpus,arm,i)
                assert result['stdout_sha256']==reference['stdout_sha256'],(corpus,arm,i)
                assert result['stderr_sha256']==reference['stderr_sha256'],(corpus,arm,i)
        a=statistics.median(x['seconds'] for x in entry['runs'] if x['arm']=='control')
        b=statistics.median(x['seconds'] for x in entry['runs'] if x['arm']=='candidate')
        entry.update(control_median=a,candidate_median=b,delta_percent=100*(b/a-1))
        print(f'V87_{corpus.upper()}_DELTA_PERCENT={entry["delta_percent"]:.4f}',flush=True)
        save()
    results['status']='COMPLETE'
    results['decision']='MEASURED_CANDIDATE__NO_RELEASE_PROMOTION'
    print('DECISION=MEASURED_CANDIDATE__NO_RELEASE_PROMOTION',flush=True)
except BaseException as e:
    results['status']='FAILED'
    results['error']=repr(e)
    save()
    raise
save()
PY
