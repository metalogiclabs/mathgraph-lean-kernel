#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1])
lib=root/'src/lib.rs'
infer=root/'src/infer.rs'

obs=r'''use crate::value::Closure;
use std::sync::{OnceLock, atomic::{AtomicU64, Ordering}};
static ENABLED: OnceLock<bool> = OnceLock::new();
static EVENT_ID: AtomicU64 = AtomicU64::new(0);
#[inline] fn enabled() -> bool { *ENABLED.get_or_init(|| std::env::var_os("MSI_Q3_TRACE").is_some()) }
#[inline]
pub(crate) fn emit(clo: &Closure<'_>) {
    if !enabled() { return; }
    let sid=EVENT_ID.fetch_add(1,Ordering::Relaxed);
    let b0=u64::from(clo.ctx.is_none());
    let b1=u64::from(clo.body.num_loose_bvars()==0);
    let b2=u64::from(clo.env.len()==0);
    let b3=(clo.body.as_ref() as *const _ as usize as u64)&7;
    let outcome=u8::from(b0==1 && b1==1);
    eprintln!("MSI_PROD|{sid:x}|{b0}|{b1}|{b2}|{b3}");
    eprintln!("MSI_RES|{sid:x}|q3|{outcome}");
}
'''
(root/'src/msi_q3.rs').write_text(obs)
s=lib.read_text()
if 'mod msi_q3;' not in s:
    pos=s.find('\n',s.find('mod ')) if 'mod ' in s else 0
    s=s[:pos+1]+'mod msi_q3;\n'+s[pos+1:]
lib.write_text(s)

s=infer.read_text()
old='''                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {'''
new='''                Value::Pi { domain, body, .. } => {\n                    crate::msi_q3::emit(body);\n                    (*domain, body)\n                },\n                _ => {'''
if old not in s:
    raise SystemExit('STAGE2_FAST_PATH_REQUIRED_FOR_Q3_TRACE')
s=s.replace(old,new,1)
infer.write_text(s)
print('Q3_TRACE_ATTACHED_ONLY_TO_STAGE2_FAST_PATH=PASS')
