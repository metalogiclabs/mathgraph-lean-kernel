#!/usr/bin/env bash
set -euo pipefail
BASE=e4ba5230f2d13ea86d8bbf71df134b446456793c
ROOT=/tmp/v99-small
rm -rf "$ROOT" && mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/checker"
git -C "$ROOT/checker" checkout -q "$BASE"

curl -fsSL https://arena.lean-lang.org/results.json -o "$ROOT/results.json"
curl -fsSL https://arena.lean-lang.org/lean-arena-tests.tar.gz -o "$ROOT/tests.tar.gz"
sha256sum "$ROOT/results.json" "$ROOT/tests.tar.gz" | tee "$ROOT/input-sha256.txt"
python3 - "$ROOT/results.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
m=x.get('meta',{})
print('V99_SMALL_ARENA_REV='+str(m.get('git_revision')))
print('V99_SMALL_ARENA_RUN='+str(m.get('github_run_id')))
PY
mkdir "$ROOT/tests"
tar -xzf "$ROOT/tests.tar.gz" -C "$ROOT/tests"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

cd "$ROOT/checker"
RUSTFLAGS='-C target-cpu=native' cargo test --release --locked -q

# Match Arena PGO training corpus.
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
arena_rev=$(python3 -c 'import json; print(json.load(open("/tmp/v99-small/results.json"))["meta"]["git_revision"])')
git -C "$ROOT/arena" checkout -q "$arena_rev"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
cd "$ROOT/checker"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$ROOT/checker/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
llvm-profdata merge -o "$ROOT/checker/pgo/merged.profdata" "$ROOT/checker/pgo"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$ROOT/checker/pgo/merged.profdata" cargo build --release --locked -q

python3 - "$ROOT" <<'PY'
import pathlib,subprocess,json,sys,time
root=pathlib.Path(sys.argv[1])
bin=root/'checker/target/release/sokonanoda'
cfg=root/'config.json'
rows=[]; failures=[]
for expected,dirname,want in [('accept','good',0),('reject','bad',1)]:
    for p in sorted((root/'tests'/dirname).rglob('*.ndjson')):
        t=time.perf_counter()
        cp=subprocess.run(['timeout','300',str(bin),str(cfg)],stdin=p.open('rb'),
                          stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        dt=time.perf_counter()-t
        row={'test':str(p.relative_to(root/'tests'/dirname)),'expected':expected,
             'exit_code':cp.returncode,'wall_time':dt,'stderr':cp.stderr.decode(errors='replace')[-2000:]}
        rows.append(row)
        if cp.returncode != want:
            failures.append(row)
            print('V99_SMALL_FAIL='+json.dumps(row),flush=True)
summary={'base':'e4ba5230f2d13ea86d8bbf71df134b446456793c',
         'num_threads':1,'count':len(rows),'failures':failures,'rows':rows}
(root/'small-gate.json').write_text(json.dumps(summary,indent=2))
print(f'V99_SMALL_COUNT={len(rows)}')
print(f'V99_SMALL_FAILURES={len(failures)}')
if failures:
    raise SystemExit(1)
print('V99_SMALL_GATE=PASS')
PY
