import hashlib
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import package_provider_zip as pack
from reconstruct_archive import verify_parts


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.original=self.root/'exact-provider.zip'
        with zipfile.ZipFile(self.original,'w') as z:
            z.writestr('compact.tar.xz.part00',b'actual fixture payload\0'*97)
        self.expected=pack.identity(self.original)
        self.args=dict(input_zip=self.original,expected_size=self.expected['bytes'],
                       expected_sha256=self.expected['sha256'],source='c'*40,run_id=39709067518,
                       artifact_id=123456789,out=self.root/'parts')

    def test_exact_roundtrip_and_delete_only_own_verification_copy(self):
        original=self.original.read_bytes()
        manifest=pack.package_zip(**self.args)
        self.assertTrue(manifest['exclusive_zip_reconstruction_and_crc_verification']['zip_crc_checked'])
        self.assertTrue(manifest['original_file_unchanged_after_all_verification'])
        self.assertFalse((self.args['out']/'exclusive-verified-original.zip').exists())
        self.assertFalse((self.args['out']/'archive.zip.xz').exists())
        self.assertEqual(self.original.read_bytes(),original)
        replay=self.root/'independently-reconstructed.zip'
        self.assertTrue(verify_parts(self.args['out']/'manifest.json',replay)['passed'])
        self.assertEqual(replay.read_bytes(),original)

    def test_keep_verification_copy(self):
        manifest=pack.package_zip(**self.args,keep_reconstructed=True)
        self.assertTrue(manifest['reconstructed_verification_duplicate_retained'])
        self.assertEqual((self.args['out']/'exclusive-verified-original.zip').read_bytes(),self.original.read_bytes())

    def test_expected_size_mismatch(self):
        self.args['expected_size']+=1
        with self.assertRaisesRegex(ValueError,'expected size mismatch'):pack.package_zip(**self.args)
        self.assertFalse(self.args['out'].exists())

    def test_expected_sha_mismatch(self):
        self.args['expected_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'expected SHA256 mismatch'):pack.package_zip(**self.args)
        self.assertFalse(self.args['out'].exists())

    def test_invalid_zip_matching_expected_hash_refused(self):
        self.original.write_bytes(b'not a ZIP')
        identity=pack.identity(self.original)
        self.args.update(expected_size=identity['bytes'],expected_sha256=identity['sha256'])
        with self.assertRaises(zipfile.BadZipFile):pack.package_zip(**self.args)
        self.assertFalse(self.args['out'].exists())

    def test_existing_destination_refused(self):
        self.args['out'].mkdir();marker=self.args['out']/'prior-evidence';marker.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'already exists'):pack.package_zip(**self.args)
        self.assertEqual(marker.read_bytes(),b'keep')

    def test_source_metadata_mutation_refused(self):
        before=pack.source_stat(self.original);after=dict(before);after['st_ctime_ns']+=1
        with mock.patch.object(pack,'source_stat',side_effect=[before,after]):
            with self.assertRaisesRegex(ValueError,'metadata changed'):pack.package_zip(**self.args)
        self.assertFalse((self.args['out']/'manifest.json').exists())

    def test_corrupted_persisted_part_refused(self):
        pack.package_zip(**self.args)
        path=next(self.args['out'].glob('archive.zip.xz.part*'))
        raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        with self.assertRaises((RuntimeError,lzma.LZMAError)):
            verify_parts(self.args['out']/'manifest.json')

    def test_48_mib_split_boundary(self):
        out=self.root/'writer';out.mkdir()
        writer=pack.PartWriter(out)
        # One emission crosses an exact part boundary. The data is not a ZIP;
        # this tests only the newly introduced bounded writer independently.
        raw=b'A'*pack.PART_BYTES+b'B'*17
        writer.emit(raw);writer.finish()
        self.assertEqual([p['bytes'] for p in writer.parts],[pack.PART_BYTES,17])
        self.assertEqual(writer.total,len(raw))
        self.assertEqual(writer.whole.hexdigest(),hashlib.sha256(raw).hexdigest())
        for part in writer.parts:
            actual=(out/part['name']).read_bytes()
            self.assertEqual(len(actual),part['bytes'])
            self.assertEqual(hashlib.sha256(actual).hexdigest(),part['sha256'])


if __name__=='__main__':unittest.main(verbosity=2)
