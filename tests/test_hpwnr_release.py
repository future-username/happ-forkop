"""Smoke-test the pinned full hpwnr binary; no real subscription or router needed."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

BINARY = os.environ.get('HPWNR_BINARY')


@unittest.skipUnless(BINARY, 'Set HPWNR_BINARY to test the actual release')
class ReleaseTests(unittest.TestCase):
    def test_crypt5_roundtrip(self):
        url = 'https://example.com/sub?key=key01&test=1'
        encrypted = subprocess.check_output([BINARY, url], text=True).strip()
        self.assertTrue(encrypted.startswith('happ://crypt5/'))
        decrypted = subprocess.check_output([BINARY, encrypted], text=True).strip()
        self.assertEqual(decrypted, url)

    def test_headers_large_stdout_and_json_conversion(self):
        observed = {}
        uuid = '00000000-0000-4000-8000-000000000001'
        outbounds = [{'protocol': 'vless', 'tag': 'Server'+str(i), 'settings': {'vnext': [{'address': 'example.com', 'port': 10000+i, 'users': [{'id': uuid, 'encryption': 'none'}]}]}, 'streamSettings': {'network': 'tcp', 'security': 'tls', 'tlsSettings': {'serverName': 'example.com'}}} for i in range(350)]
        # Exact duplicate + non-proxy sections must not pollute the URI file.
        body = json.dumps({'outbounds': outbounds+[outbounds[0], {'protocol': 'freedom', 'tag': 'direct'}], 'routing': {'rules': []}}).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed.update(dict(self.headers))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as cwd:
                    result = subprocess.run([BINARY, 'http://127.0.0.1:'+str(server.server_port)+'/sub', 'fetch', 'sb', 'uri', 'stdout', 'header', 'User-Agent', 'sing-box/1.14.0', 'header', 'X-HWID', 'test-hwid', 'header', 'X-Device-Model', 'Router Model With Spaces'], text=True, capture_output=True, cwd=cwd, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertGreater(len(result.stdout), 15000)
                    lines = result.stdout.strip().splitlines()
                    self.assertEqual(len(lines), 350)
                    self.assertEqual(len(set(lines)), 350)
                    self.assertTrue(all(line.startswith('vless://') for line in lines))
                    self.assertEqual(list(Path(cwd).iterdir()), [])
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(observed.get('User-Agent'), 'sing-box/1.14.0')
        self.assertEqual(observed.get('X-HWID'), 'test-hwid')
        self.assertEqual(observed.get('X-Device-Model'), 'Router Model With Spaces')


if __name__ == '__main__':
    unittest.main()
