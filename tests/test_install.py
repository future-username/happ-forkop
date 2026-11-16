"""Installer failures must not replace an already installed decoder."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
PINNED_X64 = '57e448bf9d2a3e6db09378943770f85006b0efb41ef7581e14f17e4eaf331486'


class InstallerTests(unittest.TestCase):
    def install(self, *, bad_hash=False, bad_help=False, download_fail=False):
        with tempfile.TemporaryDirectory() as cwd:
            root = Path(cwd)
            for part in ['etc/config', 'usr/bin', 'etc/init.d', 'tmp', 'bin', 'www/luci-static/resources/view/forkop']:
                (root/part).mkdir(parents=True, exist_ok=True)
            (root/'etc/openwrt_release').touch()
            (root/'www/luci-static/resources/view/forkop/main.js').touch()
            old = root/'usr/bin/hpwnr'
            old.write_text('previous decoder')
            payload = '#!/bin/sh\nprintf "hpwnr '+('lite v1.0.3' if bad_help else 'v1.0.3')+'\\n'+('' if bad_help else 'stdout\\n')+'"\n'
            (root/'download-payload').write_text(payload)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            scripts = {
                'bin/id': '#!/bin/sh\necho 0\n',
                'bin/uname': '#!/bin/sh\necho x86_64\n',
                'bin/uci': '#!/bin/sh\necho 2.0.0\n',
                'bin/jsonfilter': '#!/bin/sh\nexit 0\n',
                'bin/wget': '#!/bin/sh\n'+('exit 1\n' if download_fail else 'cp "$TEST_ROOT/download-payload" "$2"\n'),
                'etc/init.d/rpcd': '#!/bin/sh\nexit 0\n'
            }
            for name, content in scripts.items():
                path = root/name
                path.write_text(content)
                path.chmod(0o700)
            shutil.copytree(SOURCE/'root', root/'root')
            script = (SOURCE/'install.sh').read_text()
            script = script.replace(PINNED_X64, '0'*64 if bad_hash else digest)
            script = re.sub(r'/(?:etc|www|usr|tmp)/', lambda match: str(root)+match.group(), script)
            path = root/'install.sh'
            path.write_text(script)
            env = dict(os.environ, TEST_ROOT=str(root), PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
            result = subprocess.run(['sh', str(path)], env=env, text=True, capture_output=True)
            return result, old.read_text()

    def test_success_installs_verified_full_binary(self):
        result, binary = self.install()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('hpwnr v1.0.3', binary)
        self.assertIn('stdout', binary)

    def test_bad_checksum_preserves_previous_binary(self):
        result, binary = self.install(bad_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(binary, 'previous decoder')

    def test_wrong_variant_preserves_previous_binary(self):
        result, binary = self.install(bad_help=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(binary, 'previous decoder')

    def test_download_failure_preserves_previous_binary(self):
        result, binary = self.install(download_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(binary, 'previous decoder')


if __name__ == '__main__':
    unittest.main()
