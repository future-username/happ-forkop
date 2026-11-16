"""Exercise the real shell importer with isolated paths and fake OpenWrt tools."""
import json
import os
import re
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
if name == 'crontab':
    path = root/'crontab'
    if args == ['-l']: print(path.read_text(), end='')
    else: path.write_text(pathlib.Path(args[0]).read_text())
    sys.exit(0)
if name == 'hpwnr':
    if len(args) == 1:
        print('https://provider.example/private-token')
    else:
        (root/'fetch-args.json').write_text(json.dumps(args))
        if (root/'fetch-fail').exists(): sys.exit(1)
        print((root/'fetch-body').read_text(), end='')
    sys.exit(0)
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
    def run_import(self, *, existing=False, hwid='', defaults_fail=False,
                   mode='native', body='vless://test@example.com:443#Test\n',
                   fetch_fail=False, refresh_body=None, switch_native=False,
                   link='happ://crypt5/secret', pending_link=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for part in ['etc/config', 'etc/happ-forkop', 'usr/bin', 'var/lock', 'tmp', 'bin', 'etc/init.d']:
                (root/part).mkdir(parents=True, exist_ok=True)
            config = {'settings': {'config_version': '2.0.0'}, 'main': {'.type': 'section', 'action': 'connection'}, 'other': {'.type': 'subscription_url', 'url': 'https://other.example/sub'}}
            if existing:
                config['happ_bridge'] = {'.type': 'subscription_url', 'happ_bridge_managed': '1', 'header': ['User-Agent: Happ/4.6.0'], 'include_regex': 'Sweden', 'download_via_proxy_enabled': '1', 'download_via_proxy_section': 'working', 'override_prefix': 'My '}
            config_path = root/'etc/config/forkop'
            config_path.write_text(json.dumps(config))
            settings = root/'etc/happ-forkop/settings.json'
            form = {'link': link, 'section': 'main', 'interval': '6h', 'hwid': hwid, 'mode': mode}
            settings.write_text(json.dumps(form))
            (root/'fetch-body').write_text(body)
            if fetch_fail: (root/'fetch-fail').touch()
            (root/'etc/happ-forkop/subscription.txt').write_text('previous profile\n')
            (root/'crontab').write_text('15 1 * * * /usr/bin/unrelated\n')
            scripts = {'bin/uci': SHIM, 'bin/jsonfilter': SHIM, 'bin/crontab': SHIM, 'bin/logger': '#!/bin/sh\nexit 0\n', 'usr/bin/hpwnr': SHIM, 'etc/init.d/cron': '#!/bin/sh\nexit 0\n', 'etc/init.d/forkop': '#!/bin/sh\necho reload >> "'+str(root/'reloads')+'"\nexit 0\n', 'usr/bin/forkop': '#!/bin/sh\n' + ('exit 1\n' if defaults_fail else 'printf \'%s\\n\' \'["User-Agent: sing-box/1.14.0","X-Device-OS: OpenWrt Linux","X-HWID: generated"]\'\n')}
            for name, content in scripts.items():
                path = root/name
                path.write_text(content)
                path.chmod(0o700)
            script = (SOURCE/'root/usr/libexec/happ-forkop').read_text()
            script = re.sub(r'/(?:usr/bin|etc|var/lock|tmp)/', lambda match: str(root)+match.group(), script)
            importer = root/'import.sh'
            importer.write_text(script)
            env = dict(os.environ, TEST_ROOT=str(root), PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
            result = subprocess.run(['sh', str(importer)], env=env, text=True, capture_output=True)
            if result.returncode == 0 and refresh_body is not None:
                (root/'fetch-body').write_text(refresh_body)
                if pending_link is not None:
                    form['link'] = pending_link
                    settings.write_text(json.dumps(form))
                self.refreshed = subprocess.run(['sh', str(importer), 'refresh'], env=env, text=True, capture_output=True)
                self.assertNotIn('private-token', self.refreshed.stdout+self.refreshed.stderr)
            if result.returncode == 0 and switch_native:
                form['mode'] = 'native'
                settings.write_text(json.dumps(form))
                self.switched = subprocess.run(['sh', str(importer)], env=env, text=True, capture_output=True)
            self.profile = (root/'etc/happ-forkop/subscription.txt').read_text()
            self.cron = (root/'crontab').read_text()
            self.fetch_args = json.loads((root/'fetch-args.json').read_text()) if (root/'fetch-args.json').exists() else []
            self.reloads = len((root/'reloads').read_text().splitlines()) if (root/'reloads').exists() else 0
            self.profile_mode = (root/'etc/happ-forkop/subscription.txt').stat().st_mode & 0o777
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
        self.assertIn('Не удалось получить заголовки Forkop', result.stdout)
        self.assertEqual(before, after)

    def test_hpwnr_fetch_passes_headers_and_uses_local_provider(self):
        result, _, after = self.run_import(mode='hpwnr', hwid='my-hwid')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertTrue(after['happ_bridge']['url'].endswith('/etc/happ-forkop/subscription.txt'))
        self.assertEqual(self.profile, 'vless://test@example.com:443#Test\n')
        self.assertEqual(self.profile_mode, 0o600)
        self.assertEqual(self.fetch_args[:5], ['https://provider.example/private-token', 'fetch', 'sb', 'uri', 'stdout'])
        self.assertIn(['header', 'User-Agent', 'sing-box/1.14.0'], [self.fetch_args[i:i+3] for i in range(len(self.fetch_args))])
        self.assertIn(['header', 'X-HWID', 'my-hwid'], [self.fetch_args[i:i+3] for i in range(len(self.fetch_args))])
        self.assertNotIn('generated', self.fetch_args)
        self.assertIn('0 */6 * * * ', self.cron)
        self.assertIn('/usr/bin/unrelated', self.cron)
        self.assertEqual(self.cron.count('# happ-forkop'), 1)

    def test_large_fetch_is_not_lost(self):
        body = ''.join('vless://test@example.com:443#Server'+str(i)+'\n' for i in range(600))
        result, _, _ = self.run_import(mode='hpwnr', body=body)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertGreater(len(self.profile), 15000)
        self.assertEqual(self.profile, body)

    def test_invalid_or_failed_fetch_keeps_configuration_and_profile(self):
        for body, failed in [('', False), ('<html>504 Gateway Timeout</html>', False), ('{}\n', False), ('', True)]:
            with self.subTest(body=body, failed=failed):
                result, before, after = self.run_import(mode='hpwnr', existing=True, body=body, fetch_fail=failed)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, after)
                self.assertEqual(self.profile, 'previous profile\n')
                self.assertNotIn('# happ-forkop', self.cron)

    def test_refresh_uses_active_settings_and_reloads_changed_profile(self):
        new_body = 'trojan://test@example.com:443#New\n'
        result, _, _ = self.run_import(mode='hpwnr', refresh_body=new_body, pending_link='not-yet-valid')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.refreshed.returncode, 0, self.refreshed.stdout+self.refreshed.stderr)
        self.assertEqual(self.profile, new_body)
        self.assertEqual(self.reloads, 2)

    def test_refresh_invalid_body_keeps_previous_profile(self):
        result, _, _ = self.run_import(mode='hpwnr', refresh_body='<html>error</html>')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertNotEqual(self.refreshed.returncode, 0)
        self.assertEqual(self.profile, 'vless://test@example.com:443#Test\n')
        self.assertEqual(self.reloads, 1)

    def test_unchanged_refresh_does_not_reload(self):
        result, _, _ = self.run_import(mode='hpwnr', refresh_body='vless://test@example.com:443#Test\n')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.refreshed.returncode, 0, self.refreshed.stdout+self.refreshed.stderr)
        self.assertEqual(self.reloads, 1)

    def test_switch_back_to_native_removes_only_own_cron_entry(self):
        result, _, after = self.run_import(mode='hpwnr', switch_native=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.switched.returncode, 0, self.switched.stdout+self.switched.stderr)
        self.assertEqual(after['happ_bridge']['url'], 'https://provider.example/private-token')
        self.assertNotIn('# happ-forkop', self.cron)
        self.assertIn('/usr/bin/unrelated', self.cron)

    def test_wrappers_and_plain_https_are_accepted(self):
        for link in ['happ://add/encoded', 'v2raytun://crypt/secret', 'v2raytun://import/encoded', 'incy://import/encoded', 'https://provider.example/sub?key=key01']:
            with self.subTest(link=link):
                result, _, after = self.run_import(link=link)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                if link.startswith('https://'):
                    self.assertEqual(after['happ_bridge']['url'], link)


if __name__ == '__main__':
    unittest.main()
