from pathlib import Path
import sys

root = Path(sys.argv[1])
factor = int(sys.argv[2])
assert factor in (2, 4, 8, 16)
p = root / "src/value.rs"
s = p.read_text()

old = '''impl<'a> Env<'a> {
    pub fn lookup(&self, mut idx: u16) -> Option<V<'a>> {
        let mut cur = self;
        loop {
            match cur {
                Env::Nil { .. } => return None,
                Env::Cons { v, parent, .. } => {
                    if idx == 0 {
                        return Some(*v);
                    }
                    idx -= 1;
                    cur = parent;
                }
                Env::Framed { mask, slots, .. } => {
                    if idx >= 64 || (mask >> idx) & 1 == 0 {
                        return None;
                    }
                    let below = mask & ((1u64 << idx) - 1);
                    return Some(slots[below.count_ones() as usize]);
                }
            }
        }
    }
}'''
assert old in s

steps = []
for _ in range(factor):
    steps.append('''                        c = match c {
                            Env::Cons { parent, .. } => *parent,
                            _ => break 'fast None,
                        };''')
step_text = "\n".join(steps)

new = f'''impl<'a> Env<'a> {{
    pub fn lookup(&self, mut idx: u16) -> Option<V<'a>> {{
        let mut cur = self;
        loop {{
            if idx >= {factor} {{
                let fast = 'fast: {{
                    let mut c = cur;
{step_text}
                    break 'fast Some(c);
                }};
                if let Some(next) = fast {{
                    idx -= {factor};
                    cur = next;
                    continue;
                }}
            }}
            match cur {{
                Env::Nil {{ .. }} => return None,
                Env::Cons {{ v, parent, .. }} => {{
                    if idx == 0 {{
                        return Some(*v);
                    }}
                    idx -= 1;
                    cur = parent;
                }}
                Env::Framed {{ mask, slots, .. }} => {{
                    if idx >= 64 || (mask >> idx) & 1 == 0 {{
                        return None;
                    }}
                    let below = mask & ((1u64 << idx) - 1);
                    return Some(slots[below.count_ones() as usize]);
                }}
            }}
        }}
    }}
}}'''

s = s.replace(old, new, 1)
p.write_text(s)
