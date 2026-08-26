#!/usr/bin/env bash
set -euxo pipefail

python3 - <<'PY'
from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
old='''                    } else {\n                        self.unfold_pair(depth, t, t2)\n                    }\n'''
new='''                    } else {\n                        let lx = sx.len();\n                        let ly = sy.len();\n                        let a = lx.min(ly);\n                        let b = lx.max(ly);\n                        if a == 1 && (b == 3 || b == 4 || b == 6) {\n                            if lx < ly {\n                                let v1 = self.unfold_value(depth, t);\n                                if !std::ptr::eq(v1, t) {\n                                    return self.unify::<true>(depth, v1, t2);\n                                }\n                                let v2 = self.unfold_value(depth, t2);\n                                if !std::ptr::eq(v2, t2) {\n                                    return self.unify::<true>(depth, t, v2);\n                                }\n                            } else if ly < lx {\n                                let v2 = self.unfold_value(depth, t2);\n                                if !std::ptr::eq(v2, t2) {\n                                    return self.unify::<true>(depth, t, v2);\n                                }\n                                let v1 = self.unfold_value(depth, t);\n                                if !std::ptr::eq(v1, t) {\n                                    return self.unify::<true>(depth, v1, t2);\n                                }\n                            }\n                        }\n                        self.unfold_pair(depth, t, t2)\n                    }\n'''
anchor='''                    } else if rh.is_lt(&lh) {'''
pos=s.index(anchor)
target=s.index(old,pos)
s=s[:target]+s[target:].replace(old,new,1)
assert s.count('a == 1 && (b == 3 || b == 4 || b == 6)') == 1
p.write_text(s)
PY

cargo fmt
cargo fmt --check
cargo test --release --locked

git diff --check
git diff -- src/conv.rs

# Leave only the production change on the branch.
git config user.name 'Heath Sanchez'
git config user.email '32909488+heathsanchez@users.noreply.github.com'
git add src/conv.rs
git rm -f .github/workflows/prepare-v3-short-spine-rc.yml scripts/prepare_v3_short_spine_rc.sh
git commit -m 'Optimize equal-hint unfolding for short asymmetric spines'
git push origin HEAD:v3-short-spine-scheduling
