#!/usr/bin/env python3
"""Falsifiers for the independent public-artifact reader, not proof tests."""
import hashlib
import gzip
import json
from pathlib import Path
import tempfile
import unittest
try:
    import replay_authenticated_state as reader
except ModuleNotFoundError as error:
    if error.name != 'replay_authenticated_state':raise
    reader=None


def line(value):return json.dumps(value,separators=(',',':'),sort_keys=True).encode()+b'\n'


class ReaderTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(reader,'independent reader missing')

    def test_git_source_id_is_separate_from_content_address(self):
        source='b1931f8479a2bcd78af85ba79e60958963f89d96'
        self.assertTrue(reader.git_sha(source))
        self.assertFalse(reader.hexid(source))
        for invalid in ['a'*64,'b'*39,'G'*40,source.upper(),None,False]:
            self.assertFalse(reader.git_sha(invalid))

    def test_historical_kernel_roles_and_release_pins_refuse_substitution(self):
        bins={'producer':'delta-producer','checker':'check-selected','retained_checker':'check-selected-retained-session',
              'indexer':'export-index','index_session':'index-session','full_checker':'sokonanoda'}
        records={name:dict(path='/ci/bin/'+binary,sha256='f'*64) for name,binary in bins.items()}
        pins=dict(lean_release_binaries_sha256={name:digit*64 for name,digit in
            [('lean','a'),('leanchecker','b'),('leanchecker-paranoid','c')]})
        for name,identity in pins['lean_release_binaries_sha256'].items():
            records['original:'+name]=dict(path='/lean/bin/'+name,sha256=identity)
        summary=dict(profiles={'original':{}},binary_sha256=records)
        reader.audit_historical_tool_pins(summary,pins)
        for name,field,value in [('original:leanchecker','sha256','0'*64),
                                ('full_checker','path','/ci/bin/unrelated')]:
            changed={key:dict(record) for key,record in records.items()};changed[name][field]=value
            with self.assertRaises(ValueError):reader.audit_historical_tool_pins(dict(summary,binary_sha256=changed),pins)
        missing=dict(records);missing.pop('original:leanchecker-paranoid')
        with self.assertRaises(ValueError):reader.audit_historical_tool_pins(dict(summary,binary_sha256=missing),pins)

    def test_composition_and_newline_falsifier(self):
        name={'in':1,'str':{'pre':0,'str':'a'}}
        decl={'def':{'name':1,'type':0,'value':0}}
        new={'def':{'name':1,'type':0,'value':1}}
        base=line(name)+line({'ie':0,'nat':17})+line(decl)
        delta=line({'ie':1,'nat':23})+line(new)
        self.assertEqual(reader.compose(base,delta,['a']),line(name)+line({'ie':0,'nat':17})+delta)
        with self.assertRaises(ValueError):reader.compose(base,delta[:-1],['a'])
        with self.assertRaises(ValueError):reader.compose(base,delta,[])

    def test_address_and_member_falsifiers(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);data=b'actual';ident=hashlib.sha256(data).hexdigest()
            (root/'x').write_bytes(data)
            self.assertEqual(reader.checked_bytes(root,'x',ident),data)
            for path,identity in [('../x',ident),('x','0'*64),('/etc/passwd',ident)]:
                with self.assertRaises(ValueError):reader.checked_bytes(root,path,identity)

    def test_domain_is_not_a_public_hmac_reauthentication(self):
        envelope=dict(payload=dict(schema='expected',status='VERIFIED'),hmac_sha256='f'*64)
        self.assertEqual(reader.public_envelope(envelope,'expected')['status'],'VERIFIED')
        for altered in [dict(envelope,payload=dict(schema='other')),dict(envelope,hmac_sha256='bad')]:
            with self.assertRaises(ValueError):reader.public_envelope(altered,'expected')

    def test_metrics_falsifier(self):
        samples=[dict(apply_wall_seconds=1.0,direct_wall_seconds=2.0)]*5
        out=reader.economics(samples)
        self.assertEqual(out['median_ratio'],0.5)
        self.assertEqual(out['paired_wins'],5)
        with self.assertRaises(ValueError):reader.economics([dict(apply_wall_seconds=0,direct_wall_seconds=2)])

    def test_measured_command_and_configuration_substitution_refuses(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=reader.Store(root,{})
            snapshot=dict(path='/proc/123/fd/5',sha256='a'*64,bytes=123,seals=15)
            config=reader.canonical(reader.configuration(snapshot['path']))
            (root/'config.json').write_bytes(config)
            for name in ('stdout','stderr'):(root/name).write_bytes(b'')
            record=dict(command=['checker','config.json'],returncode=0,timed_out=False,
                stdout_path='stdout',stderr_path='stderr',stdout_sha256=reader.sha(b''),stderr_sha256=reader.sha(b''),
                input_sha256='a'*64,input_bytes=123,config_path='config.json',config_sha256=reader.sha(config))
            reader.audit_process(store,record,0,'a'*64,expected_binary='checker',snapshot=snapshot)
            for modified in [dict(record,command=['unrelated','config.json']),dict(record,input_bytes=124),
                             dict(record,config_sha256='f'*64),dict(record,command=['checker','other.json'])]:
                with self.assertRaises(ValueError):
                    reader.audit_process(store,modified,0,'a'*64,expected_binary='checker',snapshot=snapshot)
            with self.assertRaises(ValueError):
                reader.audit_process(store,record,0,'a'*64,expected_binary='checker',snapshot=dict(snapshot,seals=0))

    def test_source_manifest_cannot_omit_runtime_or_hide_modification(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            for path in ('Cargo.toml','Cargo.lock','src/lib.rs','experiments/incremental/replay_authenticated_state.py',
                         'experiments/incremental/pins.json','.github/workflows/incremental-authenticated-state.yml'):
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.encode())
            manifest={path:reader.sha((root/path).read_bytes()) for path in reader.source_inventory(root)}
            reader.audit_source_manifest(root,manifest)
            omitted=dict(manifest);omitted.pop('experiments/incremental/replay_authenticated_state.py')
            with self.assertRaises(ValueError):reader.audit_source_manifest(root,omitted)
            (root/'experiments/incremental/pins.json').write_bytes(b'changed')
            with self.assertRaises(ValueError):reader.audit_source_manifest(root,manifest)

    def test_genesis_binds_actual_policy_and_independent_source_root(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);session='session';index=dict(count=0,declarations=[]);baseline_sha='a'*64
            def put(path,value):
                raw=reader.canonical(value);target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                return reader.sha(raw)
            receipt=dict(payload=dict(schema='mathgraph.incremental-lean.v1',status='VERIFIED',export_sha256=baseline_sha,index=index),hmac_sha256='f'*64)
            receipt_raw=reader.canonical(receipt);evidence=reader.sha(receipt_raw)
            put('session/baseline-cache/records/'+evidence+'.json',receipt)
            authority=dict(payload=dict(schema='mathgraph.lean-source-owned-genesis.v1',base_evidence_id=evidence,
                source_root='b'*64,export_sha256=baseline_sha,provenance=dict(policy='exact')),hmac_sha256='f'*64)
            head=reader.sha(reader.canonical(authority));put('session/cache/genesis/'+head+'.json',authority)
            put('session/session-state.json',dict(base_evidence_id=evidence,genesis_id=head))
            genesis=dict(evidence_id=evidence,head_id=head)
            store=reader.Store(root,{})
            reader.audit_genesis(store,session,genesis,index,baseline_sha,dict(policy='exact'),'b'*64)
            for policy,source in [(dict(policy='changed'),'b'*64),(dict(policy='exact'),'c'*64)]:
                with self.assertRaises(ValueError):reader.audit_genesis(store,session,genesis,index,baseline_sha,policy,source)

    def test_omitted_negative_cannot_shrink_required_inventory(self):
        controls=[dict(name='accepted',passed=True),dict(name='rejected',passed=True)]
        summary=dict(controls=controls,required_controls=['accepted','rejected'])
        reader.audit_control_inventory(summary,{'accepted','rejected'})
        for altered in [dict(summary,controls=controls[:1]),
                        dict(controls=controls[:1],required_controls=['accepted']),
                        dict(summary,controls=[controls[0],controls[0]])]:
            with self.assertRaises(ValueError):reader.audit_control_inventory(altered,{'accepted','rejected'})

    def test_missing_exact_checked_input_refuses(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);raw=b'exact real input';compressed=gzip.compress(raw)
            path=root/'input.gz';path.write_bytes(compressed)
            descriptor=dict(encoding='gzip',artifact_relative_path='input.gz',sha256=reader.sha(compressed),
                bytes=len(compressed),uncompressed_sha256=reader.sha(raw),uncompressed_bytes=len(raw))
            store=reader.Store(root,{})
            self.assertEqual(store.blob(descriptor),raw)
            path.unlink()
            with self.assertRaises(FileNotFoundError):store.blob(descriptor)


if __name__=='__main__':unittest.main()
