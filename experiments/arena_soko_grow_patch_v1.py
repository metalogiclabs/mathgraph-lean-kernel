#!/usr/bin/env python3
"""Instrument all PtrMap growth with key identity; no checker semantic changes."""
import pathlib,sys
p=pathlib.Path(sys.argv[1])/"src/checker/ptrmap.rs"
s=p.read_text()
old="""    #[cold]
    fn grow(&mut self) {
        let n = self.tags.len() * 2;
"""
new="""    #[cold]
    fn grow(&mut self) {
        let n = self.tags.len() * 2;
        eprintln!("SOKO_ALL_GROW_CENSUS ty={} old_slots={} new_slots={} len={}",
            std::any::type_name::<K>(),self.tags.len(),n,self.len);
"""
assert s.count(old)==1, "pinned PtrMap::grow source changed"
p.write_text(s.replace(old,new))
print("CENSUS_PATCH=INSTRUMENTATION_ONLY",flush=True)
