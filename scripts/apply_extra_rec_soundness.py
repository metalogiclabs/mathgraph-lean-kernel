#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'inductive.rs'
s = p.read_text()
old = '''            // The last temporary environment extension, which also includes the recursors.\n            let recursor_extension = {'''
new = '''            // For ordinary (non-nested) inductives, the exported recursor set must be\n            // exactly the recursor set reconstructed from the inductive declaration.\n            if !st.is_nested() {\n                use std::collections::HashSet;\n                let (block_start, block_size) = self.mutual_block_sizes.get(&ind.info.name).unwrap();\n                let imported: HashSet<NamePtr<'t>> = (*block_start..(*block_start + *block_size))\n                    .filter_map(|idx| match self.declars.get_index(idx).map(|(_, d)| d) {\n                        Some(Declar::Recursor(r)) => Some(r.info.name),\n                        _ => None,\n                    })\n                    .collect();\n                let expected: HashSet<NamePtr<'t>> = recursors.iter().map(|r| r.info().name).collect();\n                assert_eq!(imported, expected, "exported recursor set differs from reconstructed recursor set");\n            }\n\n            // The last temporary environment extension, which also includes the recursors.\n            let recursor_extension = {'''
assert old in s, 'recursor extension anchor not found'
p.write_text(s.replace(old, new, 1))
print('applied exact non-nested exported recursor-set validation')
