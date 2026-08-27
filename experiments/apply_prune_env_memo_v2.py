from pathlib import Path

p = Path('src/util.rs')
s = p.read_text()
old = "pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;\npub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;"
new = "pub(crate) const PRUNE_DM_LEN: usize = 1 << 16;\npub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 16;"
if old not in s:
    raise SystemExit('prune memo constants anchor not found')
p.write_text(s.replace(old, new, 1))
print('applied prune-env memo v2: 1024 -> 65536 direct-mapped entries')
