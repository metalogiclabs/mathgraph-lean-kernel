#!/usr/bin/env python3
"""Capped partial remote ZIP reader. Never emits credentials or signed URLs."""
import binascii
import hashlib
import json
import re
import os
from pathlib import Path
import struct
import sys
import zlib
import urllib.request
import urllib.error

HERE = Path(__file__).resolve().parent
ARTIFACT_ID = 12075154855
SIZE = 4210910584
EXPECTED_FULL_SHA = '2fcf3e723403d7c34c8e06604607ec0eb69f5a04f82940bb984db9b0840898f0'
CAP = 100_000_000
API = f'https://api.github.com/repos/metalogiclabs/mathgraph-lean-kernel/actions/artifacts/{ARTIFACT_ID}/zip'


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + '\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


def http_get(url, headers, timeout):
    opener = urllib.request.build_opener(NoRedirect())
    try: return opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)
    except urllib.error.HTTPError as response: return response


class Reader:
    def __init__(self):
        self.bytes = 0
        self.requests = []
        prior = HERE / 'transfer-log.json'
        self.prior_bytes = json.loads(prior.read_text())['received_bytes'] if prior.exists() else 0
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not token:
            raise RuntimeError('native GitHub authentication unavailable')
        response = http_get(API, headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json'}, timeout=30)
        if response.status != 302 or 'Location' not in response.headers:
            raise RuntimeError(f'artifact API did not supply an authenticated redirect (HTTP {response.status})')
        self.url = response.headers['Location']
        response.close()

    def read(self, start, end):
        if not (0 <= start <= end < SIZE):
            raise ValueError('invalid archive range')
        length = end - start + 1
        if self.prior_bytes + self.bytes + length > CAP:
            raise RuntimeError('100MB cumulative transfer cap would be exceeded')
        # No GitHub authorization header is forwarded to the signed storage URL.
        with http_get(self.url, headers={'Range': f'bytes={start}-{end}',
                'Accept-Encoding': 'identity'}, timeout=60) as response:
            record = {'start': start, 'end': end, 'status': response.status,
                      'content_range': response.headers.get('Content-Range'), 'received_bytes': 0}
            self.requests.append(record)
            expected = f'bytes {start}-{end}/{SIZE}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                raise RuntimeError(f'HTTP Range unsupported or ignored (HTTP {response.status}); body was not read')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise RuntimeError('unexpected content encoding')
            data = bytearray()
            while len(data) < length:
                block = response.read(min(65536, length - len(data), CAP - self.prior_bytes - self.bytes))
                if not block: break
                self.bytes += len(block)
                record['received_bytes'] += len(block)
                if self.prior_bytes + self.bytes > CAP or len(data) + len(block) > length:
                    raise RuntimeError('range response exceeded declared bounds')
                data.extend(block)
            if len(data) != length:
                raise RuntimeError('truncated range response')
            record['sha256'] = hashlib.sha256(data).hexdigest()
            return bytes(data)

    def inventory(self):
        tail_start = max(0, SIZE - 65557)
        tail = self.read(tail_start, SIZE - 1)
        at = tail.rfind(b'PK\x05\x06')
        if at < 0 or at + 22 > len(tail):
            raise RuntimeError('ZIP end record not found')
        signature, disk, cd_disk, on_disk, count, cd_size, cd_offset, comment = struct.unpack_from('<4s4H2IH', tail, at)
        if at + 22 + comment != len(tail) or disk or cd_disk:
            raise RuntimeError('unsupported ZIP layout')
        if count == 65535 or cd_size == 0xffffffff or cd_offset == 0xffffffff:
            locator = struct.unpack_from('<4sIQI', tail, at - 20)
            if locator[0] != b'PK\x06\x07' or locator[1] != 0 or locator[3] != 1:
                raise RuntimeError('invalid ZIP64 locator')
            record = self.read(locator[2], locator[2] + 55)
            z = struct.unpack('<4sQ2H2I4Q', record)
            if z[0] != b'PK\x06\x06' or z[4] or z[5]:
                raise RuntimeError('unsupported ZIP64 layout')
            count, cd_size, cd_offset = z[7], z[8], z[9]
        central = self.read(cd_offset, cd_offset + cd_size - 1)
        (HERE / 'central-directory.bin').write_bytes(central)
        entries = []
        offset = 0
        while offset < len(central):
            fields = struct.unpack_from('<4s6H3I5H2I', central, offset)
            sig, made, needed, flags, method, mtime, mdate, crc, compressed, size, nlen, xlen, clen, disk, attrs, extattrs, local = fields
            if sig != b'PK\x01\x02' or disk:
                raise RuntimeError('invalid central directory entry')
            extra = central[offset + 46 + nlen:offset + 46 + nlen + xlen]
            name = central[offset + 46:offset + 46 + nlen].decode('utf-8' if flags & 2048 else 'cp437')
            if compressed == 0xffffffff or size == 0xffffffff or local == 0xffffffff:
                cursor = 0
                while cursor + 4 <= len(extra):
                    tag, length = struct.unpack_from('<HH', extra, cursor)
                    payload = extra[cursor + 4:cursor + 4 + length]
                    if tag == 1:
                        q = iter(struct.unpack('<' + 'Q' * (len(payload) // 8), payload[:len(payload)//8*8]))
                        if size == 0xffffffff: size = next(q)
                        if compressed == 0xffffffff: compressed = next(q)
                        if local == 0xffffffff: local = next(q)
                        break
                    cursor += 4 + length
                else:
                    raise RuntimeError('missing ZIP64 extra data')
            entries.append({'name': name, 'crc32': f'{crc:08x}', 'compressed_size': compressed,
                            'uncompressed_size': size, 'method': method, 'flags': flags,
                            'local_header_offset': local})
            offset += 46 + nlen + xlen + clen
        if len(entries) != count:
            raise RuntimeError('central directory count mismatch')
        result = {'scope': 'PARTIAL_REMOTE_ZIP_READ_FULL_ARCHIVE_SHA_NOT_VERIFIED',
                  'artifact_id': ARTIFACT_ID, 'archive_bytes': SIZE,
                  'published_full_sha256_unverified': EXPECTED_FULL_SHA,
                  'central_directory_offset': cd_offset, 'central_directory_bytes': cd_size,
                  'central_directory_sha256': hashlib.sha256(central).hexdigest(),
                  'entry_count': count, 'entries': entries}
        write('inventory.json', result)
        return result

    def member(self, entry):
        start = entry['local_header_offset']
        header = self.read(start, start + 29)
        h = struct.unpack('<4s5H3I2H', header)
        sig, needed, flags, method, mtime, mdate, crc, compressed, size, nlen, xlen = h
        if sig != b'PK\x03\x04' or method != entry['method'] or flags != entry['flags'] or flags & 1:
            raise RuntimeError('unsupported or inconsistent local header')
        names = self.read(start + 30, start + 29 + nlen + xlen)
        name = names[:nlen].decode('utf-8' if flags & 2048 else 'cp437')
        if name != entry['name']:
            raise RuntimeError('local and central member names differ')
        data_start = start + 30 + nlen + xlen
        compressed = self.read(data_start, data_start + entry['compressed_size'] - 1) if entry['compressed_size'] else b''
        if method == 0: data = compressed
        elif method == 8:
            dec = zlib.decompressobj(-15)
            data = dec.decompress(compressed, entry['uncompressed_size'] + 1)
            data += dec.flush()
            if not dec.eof or dec.unused_data or dec.unconsumed_tail:
                raise RuntimeError('invalid deflate member')
        else: raise RuntimeError('unsupported ZIP compression method')
        if len(data) != entry['uncompressed_size'] or f'{binascii.crc32(data) & 0xffffffff:08x}' != entry['crc32']:
            raise RuntimeError('retrieved member length/CRC mismatch')
        relative = Path(entry['name'])
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('unsafe member path')
        path = HERE / 'entries' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return dict(entry, raw_sha256=hashlib.sha256(data).hexdigest(),
                    compressed_sha256=hashlib.sha256(compressed).hexdigest(), crc_verified=True,
                    extracted_path=str(path.relative_to(HERE)))


def main():
    reader = None
    try:
        reader = Reader()
        if len(sys.argv) == 1 or sys.argv[1] == 'inventory':
            inv = reader.inventory()
            print(json.dumps({'status':'inventory_saved','entries':inv['entry_count'],
                              'central_directory_bytes':inv['central_directory_bytes'],'received_bytes':reader.bytes}))
        elif sys.argv[1] == 'retrieve':
            selection = json.loads((HERE / 'selection.json').read_text())
            inventory = json.loads((HERE / 'inventory.json').read_text())
            by_name = {e['name']: e for e in inventory['entries']}
            entries = [by_name[name] for name in selection['names']]
            if sum(e['compressed_size'] for e in entries) > 30_000_000:
                raise RuntimeError('selected compressed entries exceed 30MB')
            results = []
            for entry in entries:
                results.append(reader.member(entry))
                write('retrieved.json', {'scope':'PARTIAL_REMOTE_ZIP_READ_FULL_ARCHIVE_SHA_NOT_VERIFIED',
                      'entries':results, 'received_bytes_this_run':reader.bytes})
                print(json.dumps({'retrieved':entry['name'],'compressed_bytes':entry['compressed_size']}),flush=True)
        else: raise RuntimeError('expected inventory or retrieve')
    except Exception as error:
        # Exception bodies from HTTP clients may contain signed URLs. Emit only safe categories.
        kind = type(error).__name__
        safe = str(error) if isinstance(error, (RuntimeError, ValueError)) else kind
        if isinstance(error, urllib.error.URLError):
            detail = re.sub(r'https?://\S+', '[URL REDACTED]', str(error.reason))
            detail = re.sub(r'gh[pousr]_[A-Za-z0-9_]+', '[TOKEN REDACTED]', detail)
            safe = f'URLError ({type(error.reason).__name__}): {detail}' 
        safe = re.sub(r'https?://\S+', '[URL REDACTED]', safe)
        safe = re.sub(r'gh[pousr]_[A-Za-z0-9_]+', '[TOKEN REDACTED]', safe)
        write('blocker.json', {'status':'BLOCKED','error_type':kind,'error':safe,
              'scope':'PARTIAL_REMOTE_ZIP_READ_FULL_ARCHIVE_SHA_NOT_VERIFIED',
              'received_bytes_this_run':reader.bytes if reader else 0,
              'requests':reader.requests if reader else []})
        print(json.dumps({'status':'BLOCKED','error':safe}))
        raise SystemExit(2)
    finally:
        if reader:
            prior_path = HERE / 'transfer-log.json'
            prior = json.loads(prior_path.read_text()) if prior_path.exists() else {'requests':[], 'received_bytes':0}
            prior['requests'].extend(reader.requests)
            prior['received_bytes'] += reader.bytes
            write('transfer-log.json', prior)

if __name__ == '__main__': main()
