"""Exercise the real shell importer with isolated paths and fake OpenWrt tools."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]

SHIM = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ['TEST_ROOT'])
if name == 'jsonfilter':
    data = json.loads(args[args.index('-s')+1]) if '-s' in args else json.loads(pathlib.Path(args[args.index('-i')+1]).read_text())
    expr = args[args.index('-e')+1]
    if expr == '@[*]':
        print('\n'.join(data))
    else:
        key = expr[2:]
        if key not in data: sys.exit(1)
        print(data[key])
    sys.exit(0)
if name == 'uci':
    directory = pathlib.Path(args[args.index('-c')+1]) if '-c' in args else root/'etc/config'
    for flag in ['-c', '-t']:
        if flag in args:
            i = args.index(flag); del args[i:i+2]
    args = [a for a in args if a != '-q']
    command = args[0]
    if command == 'changes': sys.exit(0)
    path = directory/'forkop'
    data = json.loads(path.read_text())
    if command == 'commit': sys.exit(0)
    target, sep, value = args[1].partition('=')
    parts = target.split('.')
    section = parts[1]
    key = parts[2] if len(parts) > 2 else '.type'
    if command == 'get':
        if section not in data or key not in data[section]: sys.exit(1)
        print(data[section][key]); sys.exit(0)
    if command == 'set': data.setdefault(section, {})[key] = value
    if command == 'add_list': data[section].setdefault(key, []).append(value)
    if command == 'delete':
        if len(parts) == 2: data.pop(section, None)
        else: data[section].pop(key, None)
    path.write_text(json.dumps(data))
'''


class ImportTests(unittest.TestCase):
    def run_import(self, *, existing=False, hwid='', defaults_fail=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for part in ['etc/config', 'etc/happ-forkop', 'usr/bin', 'var/lock', 'tmp', 'bin', 'etc/init.d']:
                (root/part).mkdir(parents=True, exist_ok=True)
            config = {'settings': {'config_version': '2.0.0'}, 'main': {'.type': 'section', 'action': 'connection'}, 'other': {'.type': 'subscription_url', 'url': 'https://other.example/sub'}}
            if existing:
                config['happ_bridge'] = {'.type': 'subscription_url', 'happ_bridge_managed': '1', 'header': ['User-Agent: Happ/4.6.0'], 'include_regex': 'Sweden', 'download_via_proxy_enabled': '1', 'download_via_proxy_section': 'working', 'override_prefix': 'My '}
            config_path = root/'etc/config/forkop'
            config_path.write_text(json.dumps(config))
            (root/'etc/happ-forkop/settings.json').write_text(json.dumps({'link': 'happ://crypt5/secret', 'section': 'main', 'interval': '6h', 'hwid': hwid}))
            scripts = {'bin/uci': SHIM, 'bin/jsonfilter': SHIM, 'usr/bin/hpwnr': '#!/bin/sh\nprintf "%s\\n" "https://provider.example/private-token"\n', 'etc/init.d/forkop': '#!/bin/sh\nexit 0\n', 'usr/bin/forkop': '#!/bin/sh\n' + ('exit 1\n' if defaults_fail else 'printf \'%s\\n\' \'["User-Agent: sing-box/1.14.0","X-Device-OS: OpenWrt Linux","X-HWID: generated"]\'\n')}
            for name, content in scripts.items():
                path = root/name
                path.write_text(content)
                path.chmod(0o700)
            script = (SOURCE/'root/usr/libexec/happ-forkop').read_text()
            for prefix in ['/usr/bin/', '/etc/', '/var/lock/', '/tmp/']:
                script = script.replace(prefix, str(root)+prefix)
            importer = root/'import.sh'
            importer.write_text(script)
            env = dict(os.environ, TEST_ROOT=str(root), PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
            result = subprocess.run(['sh', str(importer)], env=env, text=True, capture_output=True)
            self.assertFalse((root/'var/lock/happ-forkop.lock').exists())
            self.assertNotIn('private-token', result.stdout+result.stderr)
            return result, config, json.loads(config_path.read_text())

    def test_new_import_uses_core_headers(self):
        result, before, after = self.run_import()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(after['other'], before['other'])
        headers = after['happ_bridge']['header']
        self.assertIn('User-Agent: sing-box/1.14.0', headers)
        self.assertIn('X-HWID: generated', headers)
        self.assertEqual(after['happ_bridge']['subscription_update_interval'], '6h')

    def test_reimport_preserves_user_options_and_overrides_hwid(self):
        result, before, after = self.run_import(existing=True, hwid='custom-hwid')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        for key in ['include_regex', 'download_via_proxy_enabled', 'download_via_proxy_section', 'override_prefix']:
            self.assertEqual(after['happ_bridge'][key], before['happ_bridge'][key])
        headers = after['happ_bridge']['header']
        self.assertEqual(sum(h.startswith('X-HWID:') for h in headers), 1)
        self.assertIn('X-HWID: custom-hwid', headers)
        self.assertNotIn('User-Agent: Happ/4.6.0', headers)

    def test_header_failure_leaves_configuration_unchanged(self):
        result, before, after = self.run_import(existing=True, defaults_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
