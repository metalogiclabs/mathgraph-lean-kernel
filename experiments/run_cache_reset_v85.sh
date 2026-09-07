#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v85
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cd "$ROOT/base"
test "$(git rev-parse HEAD)" = "$BASE"
python3 - <<'PY'
from pathlib import Path
import re
p=Path('src/util.rs')
s=p.read_text()
a=s.index('    pub(crate) fn clear(&mut self) {',s.index("impl<'a, 't> TcCache"))
b=s.index('    pub(crate) fn clear_session(&mut self)',a)
old=s[a:b]
# Only the per-declaration cache reset changes. All entries are still invalidated.
new=old
new=re.sub(r'self\.(\w+)\.clear\(\);',r'shrink_map(&mut self.\1);',new)
for field in ('conv_cache_pos','conv_cache_neg','conv_cache_neg_probe','open_eval_seen','iota_stuck','fvar_cache','ind_occ_cache'):
    new=new.replace('shrink_map(&mut self.'+field+');','shrink_set(&mut self.'+field+');')
new=new.replace('shrink_map(&mut self.frames);','if self.frames.capacity() > KEEP_CAP {\n            self.frames = hashbrown::HashTable::new();\n        } else {\n            self.frames.clear();\n        }')
assert 'self.prune_dm.fill((0, 0, None));' in new
assert 'self.frames.clear();' in new
assert old != new
s=s[:a]+new+s[b:]
p.write_text(s)
PY
export RUSTFLAGS='-C target-cpu=native'
cargo build --release --locked -q
cp target/release/sokonanoda "$ROOT/checker"
git diff --check
set +e
cargo test --locked -q > "$ROOT/out/baseline-tests.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$ROOT/out/baseline-tests.rc"
echo "V85_TEST_RC=$rc"
if [ "$rc" -ne 0 ]; then echo 'V85_QUALIFICATION=FAILED'; fi
# Build the untouched control with identical compiler settings.
git worktree add -q --detach "$ROOT/control" "$BASE"
cd "$ROOT/control"
cargo build --release --locked -q
cp target/release/sokonanoda "$ROOT/control-checker"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib,sys
r=Path(sys.argv[1])
for c in ('std','cedar','mathlib'):
 p=r/'arena'/'_build'/'tests'/f'{c}.ndjson'
 assert p.stat().st_size>0
 print(f'V85_{c.upper()}_SHA256={hashlib.sha256(p.read_bytes()).hexdigest()}')
PY
cd "$ROOT"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import subprocess,sys,hashlib,json,time,os,statistics,random
r=Path(sys.argv[1]); out=r/'out'; cfg=r/'config.json'
results={}
for corpus in ('std','cedar','mathlib'):
    data=(r/'arena'/'_build'/'tests'/f'{corpus}.ndjson').read_bytes()
    def run(binary, suffix):
        start=time.perf_counter()
        p=subprocess.run([str(binary),str(cfg)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200)
        elapsed=time.perf_counter()-start
        (out/f'{corpus}.{suffix}.stdout').write_bytes(p.stdout)
        (out/f'{corpus}.{suffix}.stderr').write_bytes(p.stderr)
        return {'rc':p.returncode,'seconds':elapsed,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    reference=run(r/'control-checker','reference')
    candidate=run(r/'checker','candidate')
    assert reference['rc']==candidate['rc']==0,(corpus,reference,candidate)
    assert reference['stdout_sha256']==candidate['stdout_sha256'],corpus
    assert reference['stderr_sha256']==candidate['stderr_sha256'],corpus
    print(f'V85_{corpus.upper()}_EXACT_REPLAY=PASS',flush=True)
    rows=[]
    for i in range(5):
        order=['control','candidate'] if i%2==0 else ['candidate','control']
        for arm in order:
            binary=r/('control-checker' if arm=='control' else 'checker')
            result=run(binary,f'{arm}.{i}')
            assert result['rc']==0
            assert result['stdout_sha256']==reference['stdout_sha256']
            assert result['stderr_sha256']==reference['stderr_sha256']
            rows.append({'pass':i,'arm':arm,**result})
    a=statistics.median(x['seconds'] for x in rows if x['arm']=='control')
    b=statistics.median(x['seconds'] for x in rows if x['arm']=='candidate')
    results[corpus]={'reference':reference,'candidate':candidate,'runs':rows,'control_median':a,'candidate_median':b,'delta_percent':100*(b/a-1)}
    print(f'V85_{corpus.upper()}_DELTA_PERCENT={100*(b/a-1):.4f}',flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2))
print('DECISION=MEASURED_CANDIDATE__NO_RELEASE_PROMOTION',flush=True)
PY
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
