from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from addon_packages import read_package
import update_repo


REPOSITORY = Path(__file__).resolve().parents[1]


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def make_package(directory, version='1.0.0', codename='Omega', platform='linux-armv7',
                 addon_id='vfs.stream.fast', marker='', legacy=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    root = ET.Element('addon', id=addon_id, version=version, name=addon_id)
    requires = ET.SubElement(root, 'requires')
    main = '2.0.4' if codename == 'Piers' else '2.0.2'
    ET.SubElement(requires, 'import', addon='kodi.binary.global.main', version=main)
    metadata = ET.SubElement(root, 'extension', point='xbmc.addon.metadata')
    ET.SubElement(metadata, 'platform').text = 'all'
    ET.SubElement(metadata, 'summary').text = marker or f'{codename}-{platform}'
    parts = [addon_id, version]
    if codename and not legacy:
        parts.append(codename)
    if platform != 'all':
        parts.append(platform)
    target = directory / ('-'.join(parts) + '.zip')
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr(f'{addon_id}/addon.xml', ET.tostring(root))
        archive.writestr(f'{addon_id}/icon.png', b'fixture')
    return target


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def generate(self):
        shutil.copy2(REPOSITORY / 'addon.xml', self.base / 'addon.xml')
        result = subprocess.run([sys.executable, str(REPOSITORY / 'generate_repo.py')],
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return {name: ET.parse(self.base / path).getroot() for name, path in (
            ('common', 'addons.xml'), ('Omega', 'omega/addons.xml'),
            ('Piers', 'piers/addons.xml'))}

    def test_import_keeps_both_kodi_builds_and_uses_manifest_version(self):
        assets = self.base / 'assets'
        packages = [make_package(assets, codename=name) for name in ('Omega', 'Piers')]
        work = self.base / 'work'
        work.mkdir()

        def gh(command, **kwargs):
            self.assertIsInstance(command, list)
            if command[:2] == ['gh', 'api']:
                if command[2].endswith('/latest'):
                    response = {'id': 99, 'tag_name': 'v99.0.0'}
                else:
                    response = [[{'name': p.name, 'size': p.stat().st_size,
                                  'digest': 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()}
                                 for p in packages]]
                return subprocess.CompletedProcess(command, 0, json.dumps(response))
            destination = Path(command[command.index('--dir') + 1])
            for package in packages:
                shutil.copy2(package, destination / package.name)
            return subprocess.CompletedProcess(command, 0)

        with working_directory(work), patch.object(update_repo.subprocess, 'run', side_effect=gh):
            update_repo.download_release('https://github.com/forbxy/vfs.stream.fast')
        installed = list((work / 'vfs.stream.fast').glob('*.zip'))
        self.assertEqual({p.name for p in installed}, {p.name for p in packages})
        for package in installed:
            self.assertEqual(package.read_bytes(), (assets / package.name).read_bytes())

    def test_legacy_vfs_is_omega_and_unknown_codename_is_rejected(self):
        old = make_package(self.base, legacy=True)
        self.assertEqual(read_package(old).codename, 'Omega')
        self.assertIn('-Omega-', read_package(old).filename)
        unknown = make_package(self.base, codename='Nexus')
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            read_package(unknown)

    def test_shared_addons_and_independent_vfs_versions_and_metadata(self):
        vfs = self.base / 'vfs.stream.fast'
        make_package(vfs, version='1.9.0', legacy=True)
        for platform in ('linux-armv7', 'linux-x86_64', 'linux-aarch64'):
            make_package(vfs, version='1.10.0', platform=platform, marker=f'Omega {platform}')
            make_package(vfs, version='1.2.0', codename='Piers', platform=platform,
                         marker=f'Piers {platform}')
        generic = make_package(self.base / 'plugin.test', version='2.0.0', codename=None,
                               platform='all', addon_id='plugin.test')
        # Previous repository ZIPs must not introduce duplicate/old repo entries.
        make_package(self.base / 'repository.forbxy', version='1.2.0', codename=None,
                     platform='all', addon_id='repository.forbxy')
        trees = self.generate()
        common = trees['common']
        self.assertEqual([a.get('id') for a in common],
                         ['plugin.test', 'repository.forbxy', 'repository.forbxy.ghproxy'])
        self.assertEqual(common.find("addon[@id='plugin.test']").get('version'), '2.0.0')
        self.assertTrue(generic.exists())
        for name, version, main in (('Omega', '1.10.0', '2.0.2'), ('Piers', '1.2.0', '2.0.4')):
            entries = list(trees[name])
            self.assertEqual(len(entries), 3)
            self.assertEqual({a.get('version') for a in entries}, {version})
            for entry in entries:
                self.assertEqual(entry.get('id'), 'vfs.stream.fast')
                self.assertEqual(entry.find("requires/import[@addon='kodi.binary.global.main']").get('version'), main)
                metadata = entry.find("extension[@point='xbmc.addon.metadata']")
                platform = metadata.findtext('platform').split()[0]
                self.assertEqual(metadata.findtext('summary'), f'{name} {platform}')
                path = metadata.findtext('path')
                self.assertIn(f'-{name}-', path)
                self.assertTrue((self.base / path).is_file())
            self.assertEqual(entries[-1].findtext("extension[@point='xbmc.addon.metadata']/platform"),
                             'linux-armv7 linux')
        for relative in ('addons.xml', 'omega/addons.xml', 'piers/addons.xml'):
            data = (self.base / relative).read_bytes()
            self.assertEqual((self.base / f'{relative}.md5').read_text(), hashlib.md5(data).hexdigest())

    def test_legacy_packages_never_fill_empty_piers_index(self):
        make_package(self.base / 'vfs.stream.fast', legacy=True)
        trees = self.generate()
        self.assertEqual(len(trees['Omega']), 1)
        self.assertEqual(len(trees['Piers']), 0)
        self.assertIsNone(trees['common'].find("addon[@id='vfs.stream.fast']"))

    def test_named_omega_package_wins_over_legacy_at_same_version(self):
        directory = self.base / 'vfs.stream.fast'
        make_package(directory, legacy=True, marker='old')
        make_package(directory, marker='named')
        trees = self.generate()
        self.assertEqual(len(trees['Omega']), 1)
        self.assertEqual(trees['Omega'][0].findtext("extension[@point='xbmc.addon.metadata']/summary"), 'named')

    def test_repository_zips_and_proxy_routes_cover_prereleases(self):
        self.generate()
        for addon_id in ('repository.forbxy', 'repository.forbxy.ghproxy'):
            with self.subTest(repository=addon_id):
                package = self.base / f'{addon_id}-1.3.0.zip'
                self.assertEqual(package.read_bytes(),
                                 (self.base / addon_id / package.name).read_bytes())
                with zipfile.ZipFile(package) as archive:
                    root = ET.fromstring(archive.read(f'{addon_id}/addon.xml'))
                directories = root.findall("extension[@point='xbmc.addon.repository']/dir")
                for api, codename in (('21.0.0', 'omega'), ('21.3.0', 'omega'),
                                      ('21.90.701', 'piers'), ('21.90.801', 'piers'),
                                      ('21.90.901', 'piers'), ('22.0.0', 'piers'),
                                      ('22.2.0', 'piers')):
                    current = tuple(map(int, api.split('.')))
                    selected = [d for d in directories if
                                (not d.get('minversion') or current >= tuple(map(int, d.get('minversion').split('.')))) and
                                (not d.get('maxversion') or current <= tuple(map(int, d.get('maxversion').split('.'))))]
                    self.assertEqual(len(selected), 2, api)
                    self.assertTrue(selected[0].findtext('info').endswith('/master/addons.xml') or
                                    selected[0].findtext('info') == 'https://kodi8.com/addons.xml')
                    self.assertTrue(selected[1].findtext('info').endswith(f'/{codename}/addons.xml'))
                for directory in directories:
                    if addon_id.endswith('.ghproxy'):
                        self.assertTrue(directory.findtext('info').startswith('https://kodi8.com/'))
                        self.assertTrue(directory.findtext('checksum').startswith('https://kodi8.com/'))
                        self.assertTrue(directory.findtext('datadir').startswith('https://gh-proxy.org/'))


if __name__ == '__main__':
    unittest.main()
