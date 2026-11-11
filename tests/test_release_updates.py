import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import update_repo
from test_repository import make_package, working_directory


SOURCE = 'https://github.com/forbxy/vfs.stream.fast'


class ReleaseUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.work = self.base / 'work'
        self.work.mkdir()
        self.packages = [make_package(self.base / 'release', marker='cloud')]
        self.downloads = []
        self.assets = []

    def published_assets(self):
        return self.assets or [dict(name=package.name, size=package.stat().st_size,
                                   digest='sha256:' + update_repo.sha256(package), state='uploaded')
                               for package in self.packages]

    def gh(self, command, **kwargs):
        if command[:2] == ['gh', 'api']:
            if command[2].endswith('/latest'):
                response = {'id': 99, 'tag_name': 'v99.0.0'}
            else:
                self.assertIn('--paginate', command)
                self.assertIn('--slurp', command)
                # Multiple pages must all be considered, including unchanged assets.
                response = [[asset] for asset in self.published_assets()]
            return subprocess.CompletedProcess(command, 0, json.dumps(response))
        self.assertEqual(command[:3], ['gh', 'release', 'download'])
        self.downloads.append(command)
        destination = Path(command[command.index('--dir') + 1])
        patterns = [command[index + 1] for index, value in enumerate(command) if value == '--pattern']
        for package in self.packages:
            if package.name in patterns:
                shutil.copy2(package, destination / package.name)
        return subprocess.CompletedProcess(command, 0)

    def check_release(self):
        with working_directory(self.work), patch.object(update_repo.subprocess, 'run', side_effect=self.gh):
            return update_repo.download_release(SOURCE)

    def install(self, package=None, directory='vfs.stream.fast', name=None):
        package = package or self.packages[0]
        destination = self.work / directory / (name or package.name)
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(package, destination)
        return destination

    def snapshot(self):
        return {str(path.relative_to(self.work)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.work.rglob('*') if path.is_file()}

    def test_unchanged_content_does_not_download_or_touch_the_repository(self):
        self.install()
        (self.work / 'addons.xml').write_text('existing index')
        before = self.snapshot()
        self.assertFalse(self.check_release())
        self.assertEqual(self.downloads, [])
        self.assertEqual(self.snapshot(), before)

    def test_same_version_and_size_with_different_bytes_uses_release(self):
        installed = make_package(self.work / 'vfs.stream.fast', marker='local')
        self.assertEqual(installed.stat().st_size, self.packages[0].stat().st_size)
        self.assertNotEqual(installed.read_bytes(), self.packages[0].read_bytes())
        self.assertTrue(self.check_release())
        self.assertEqual(installed.read_bytes(), self.packages[0].read_bytes())

    def test_missing_package_is_downloaded_and_the_next_check_is_idle(self):
        self.assertTrue(self.check_release())
        self.assertEqual(len(self.downloads), 1)
        before = self.snapshot()
        self.assertFalse(self.check_release())
        self.assertEqual(len(self.downloads), 1)
        self.assertEqual(self.snapshot(), before)

    def test_new_version_keeps_old_packages(self):
        old = make_package(self.work / 'vfs.stream.fast', version='0.9.0')
        original = old.read_bytes()
        self.assertTrue(self.check_release())
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual((self.work / 'vfs.stream.fast' / self.packages[0].name).read_bytes(),
                         self.packages[0].read_bytes())

    def test_downloads_only_changed_assets_across_pages(self):
        self.packages.append(make_package(self.base / 'release', codename='Piers'))
        self.install()
        self.assertTrue(self.check_release())
        command = self.downloads[0]
        names = [command[index + 1] for index, value in enumerate(command) if value == '--pattern']
        self.assertEqual(names, [self.packages[1].name])

    def test_legacy_vfs_already_stored_as_omega_is_not_downloaded(self):
        self.packages = [make_package(self.base / 'legacy', legacy=True)]
        name = self.packages[0].name.replace('-linux-', '-Omega-linux-')
        self.install(name=name)
        self.assertFalse(self.check_release())
        self.assertEqual(self.downloads, [])

    def test_matching_archive_in_the_wrong_directory_does_not_hide_a_missing_package(self):
        misplaced = self.install(directory='wrong-addon')
        self.assertTrue(self.check_release())
        self.assertTrue(misplaced.is_file())
        self.assertTrue((self.work / 'vfs.stream.fast' / self.packages[0].name).is_file())

    def test_all_checksums_are_validated_before_any_package_is_replaced(self):
        installed = make_package(self.work / 'vfs.stream.fast', marker='local')
        self.packages.append(make_package(self.base / 'release', codename='Piers'))
        self.assets = self.published_assets()
        self.assets[1]['digest'] = 'sha256:' + '0' * 64
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.check_release()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(installed.exists())

    def test_wrong_download_size_never_installs(self):
        self.assets = self.published_assets()
        self.assets[0]['size'] += 1
        with self.assertRaisesRegex(ValueError, 'size mismatch'):
            self.check_release()
        self.assertEqual(self.snapshot(), {})

    def test_missing_digest_fails_without_downloading(self):
        self.assets = self.published_assets()
        self.assets[0]['digest'] = None
        with self.assertRaisesRegex(ValueError, 'Missing or invalid release SHA-256'):
            self.check_release()
        self.assertEqual(self.downloads, [])
        self.assertEqual(self.snapshot(), {})

    def test_incomplete_uploads_and_non_zip_assets_are_skipped(self):
        self.assets = self.published_assets()
        self.assets[0]['state'] = 'starter'
        self.assets.append({'name': 'checksums.txt'})
        self.assertFalse(self.check_release())
        self.assertEqual(self.downloads, [])

    def test_no_release_is_skipped_but_api_failures_are_not_silenced(self):
        for code in (404, 403, 500):
            with self.subTest(status=code), working_directory(self.work), patch.object(
                    update_repo.subprocess, 'run', side_effect=subprocess.CalledProcessError(
                        1, ['gh', 'api'], stderr=f'gh: API error (HTTP {code})')):
                if code == 404:
                    self.assertFalse(update_repo.download_release(SOURCE))
                else:
                    with self.assertRaises(subprocess.CalledProcessError):
                        update_repo.download_release(SOURCE)
        self.assertEqual(self.snapshot(), {})

    def test_no_changes_emit_false_for_the_workflow(self):
        (self.work / 'sources.txt').write_text('# sources\n' + SOURCE + '\n')
        output = self.base / 'github-output'
        with working_directory(self.work), patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), \
                patch.object(update_repo, 'download_release', return_value=False):
            self.assertFalse(update_repo.main())
        self.assertEqual(output.read_text(), 'changed=false\n')

    def test_checks_every_source_even_after_finding_an_update(self):
        (self.work / 'sources.txt').write_text(SOURCE + '\nhttps://github.com/forbxy/example\n')
        output = self.base / 'github-output'
        with working_directory(self.work), patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), \
                patch.object(update_repo, 'download_release', side_effect=[True, False]) as download:
            self.assertTrue(update_repo.main())
        self.assertEqual(download.call_count, 2)
        self.assertEqual(output.read_text(), 'changed=true\n')

    def test_failed_source_does_not_emit_a_success_output(self):
        (self.work / 'sources.txt').write_text(SOURCE + '\nhttps://github.com/forbxy/example\n')
        output = self.base / 'github-output'
        with working_directory(self.work), patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), \
                patch.object(update_repo, 'download_release', side_effect=[True, ValueError('bad archive')]):
            with self.assertRaisesRegex(RuntimeError, 'Failed to update'):
                update_repo.main()
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
