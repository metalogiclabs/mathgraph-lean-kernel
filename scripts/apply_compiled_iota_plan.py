#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path('.')
util=root/'src'/'util.rs'
s=util.read_text()
old="""    pub(crate) rec_rule_cache: FxHashMap<(ExprPtr<'t>, LevelsPtr<'t>), V<'a>>,"""
new=old+"\n    pub(crate) iota_plan_cache: FxHashMap<(NamePtr<'t>, NamePtr<'t>, usize, usize), (ExprPtr<'t>, u16, usize, usize)>,"
assert old in s
s=s.replace(old,new,1)
old="""            rec_rule_cache: small_fx_hash_map(),"""
new=old+"\n            iota_plan_cache: small_fx_hash_map(),"
assert old in s
s=s.replace(old,new,1)
old="""        self.rec_rule_cache.clear();"""
new=old+"\n        self.iota_plan_cache.clear();"
assert old in s
s=s.replace(old,new,1)
old="""        shrink_map(&mut self.rec_rule_cache);"""
new=old+"\n        shrink_map(&mut self.iota_plan_cache);"
assert old in s
s=s.replace(old,new,1)
util.write_text(s)

evalp=root/'src'/'eval.rs'
e=evalp.read_text()
old="""        let rec_rule = rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?;
        let num_extra = ctor_args.len().checked_sub(usize::from(rec_rule.ctor_telescope_size_wo_params))?;
        let cache_key = (rec_rule.val, levels);
        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {"""
new="""        let pkey = (rec.info.name, ctor_name, ctor_args.len(), args.len());
        let (rule_val, rule_tel, nprefix, major_idx) = match self.tc_cache.iota_plan_cache.get(&pkey).copied() {
            Some(p) => p,
            None => {
                let rr = rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?;
                let p = (rr.val, rr.ctor_telescope_size_wo_params,
                    usize::from(rec.num_params + rec.num_motives + rec.num_minors), rec.major_idx());
                self.tc_cache.iota_plan_cache.insert(pkey, p);
                p
            }
        };
        let num_extra = ctor_args.len().checked_sub(usize::from(rule_tel))?;
        let cache_key = (rule_val, levels);
        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {"""
assert old in e
e=e.replace(old,new,1)
old="""                let v = self.eval_inst(rec_rule.val, rec.info.uparams, levels);"""
new="""                let v = self.eval_inst(rule_val, rec.info.uparams, levels);"""
assert old in e
e=e.replace(old,new,1)
old="""        let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);
        result = self.apply_many(depth, result, &args[..nprefix]);
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);"""
new="""        result = self.apply_many(depth, result, &args[..nprefix]);
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[major_idx + 1..]);"""
assert old in e
e=e.replace(old,new,1)
evalp.write_text(e)
print('compiled iota plan applied')
