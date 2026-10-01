import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from compute_tokens import sources


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        self.payload = b'public dataset fixture'
        self.spec = dict(filename='fixture.bin', bytes=len(self.payload),
                         sha256=hashlib.sha256(self.payload).hexdigest(), url='https://example.invalid/pinned')
        (self.root/'sources.json').write_text(json.dumps({'fixture':self.spec}))
        self.patcher = patch.object(sources, 'DATA', self.root)
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def response(self, payload, status=200, offset=0):
        r = io.BytesIO(payload); r.status = status
        r.headers = {'Content-Range':f'bytes {offset}-{len(self.payload)-1}/{len(self.payload)}'}
        return r

    def test_missing_requires_download_opt_in(self):
        with patch.object(sources.urllib.request, 'urlopen') as fetch:
            with self.assertRaises(FileNotFoundError): sources.acquire(self.raw)
            fetch.assert_not_called()

    def test_download_and_verify_existing_without_network(self):
        with patch.object(sources.urllib.request, 'urlopen', return_value=self.response(self.payload)):
            sources.acquire(self.raw, True)
        with patch.object(sources.urllib.request, 'urlopen') as fetch:
            sources.acquire(self.raw)
            fetch.assert_not_called()

    def test_resume(self):
        (self.raw/'fixture.bin.part').write_bytes(self.payload[:5])
        with patch.object(sources.urllib.request, 'urlopen', return_value=self.response(self.payload[5:],206,5)) as fetch:
            sources.acquire(self.raw, True)
            self.assertEqual(fetch.call_args.args[0].get_header('Range'), 'bytes=5-')
        self.assertEqual((self.raw/'fixture.bin').read_bytes(), self.payload)

    def test_server_ignoring_resume_preserves_partial(self):
        path = self.raw/'fixture.bin.part'; path.write_bytes(self.payload[:5])
        with patch.object(sources.urllib.request, 'urlopen', return_value=self.response(self.payload)):
            with self.assertRaises(RuntimeError): sources.acquire(self.raw, True)
        self.assertEqual(path.read_bytes(), self.payload[:5])

    def test_corrupt_download_not_promoted(self):
        with patch.object(sources.urllib.request, 'urlopen', return_value=self.response(b'bad')):
            with self.assertRaises(ValueError): sources.acquire(self.raw, True)
        self.assertFalse((self.raw/'fixture.bin').exists())
        self.assertTrue((self.raw/'fixture.bin.part').exists())

    def test_disk_reserve(self):
        with patch.object(sources.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaises(OSError): sources.acquire(self.raw, True)
