"""Import changed ZIP assets from each source's latest GitHub Release."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from addon_packages import get_platform_from_filename, read_package


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def latest_release(repo_name):
    endpoint = f'repos/{repo_name}/releases/latest'
    try:
        result = subprocess.run(['gh', 'api', endpoint],
                                check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        if '(HTTP 404)' not in (error.stderr or ''):
            raise
        print(f'No published release in {repo_name}; skipping')
        return None
    release = json.loads(result.stdout)
    # The dedicated endpoint handles releases with more than one page of assets.
    result = subprocess.run(
        ['gh', 'api', f"repos/{repo_name}/releases/{release['id']}/assets?per_page=100",
         '--paginate', '--slurp'], check=True, capture_output=True, text=True,
    )
    release['assets'] = [asset for page in json.loads(result.stdout) for asset in page]
    return release


def asset_digest(asset):
    digest = asset.get('digest') or ''
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
        raise ValueError(f"Missing or invalid release SHA-256 for {asset['name']}")
    return digest.partition(':')[2].lower()


def matching_package(asset):
    """A matching version is insufficient: the complete ZIP must match."""
    digest = asset_digest(asset)
    name = asset['name']
    names = {name}
    # Old VFS releases have no Kodi codename; the repository stores them as Omega.
    platform = get_platform_from_filename(name)
    suffix = f'-{platform}.zip'
    if name.startswith('vfs.stream.fast-') and platform != 'all' and not any(
            f'-{codename}-' in name for codename in ('Omega', 'Piers')):
        names.add(name[:-len(suffix)] + '-Omega' + suffix)
    for path in Path('.').glob('*/*.zip'):
        if path.name not in names or path.stat().st_size != asset['size']:
            continue
        if sha256(path) != digest:
            continue
        package = read_package(path)
        if path == Path(package.addon_id) / package.filename:
            return True
    return False


def download_release(repo_url):
    repo_name = repo_url.removeprefix('https://github.com/').strip().rstrip('/')
    print(f'Checking {repo_name}...')
    release = latest_release(repo_name)
    if release is None:
        return False
    print(f"Latest release: {release['tag_name']}")
    assets = [asset for asset in release['assets']
              if asset['name'].endswith('.zip') and asset.get('state', 'uploaded') == 'uploaded']
    if not assets:
        print(f'No ZIP assets in {repo_name}')
        return False
    pending = [asset for asset in assets if not matching_package(asset)]
    if not pending:
        print(f'Packages unchanged in {repo_name}')
        return False

    changed = False
    with tempfile.TemporaryDirectory(prefix='forbxy-release-') as temporary:
        command = ['gh', 'release', 'download', release['tag_name'], '--repo', repo_name,
                   '--dir', temporary]
        for asset in pending:
            name = asset['name']
            if Path(name).name != name or '\\' in name:
                raise ValueError(f'Invalid release filename: {name}')
            command.extend(['--pattern', name])
        subprocess.run(command, check=True)

        # Validate every downloaded asset before replacing any installed package.
        replacements = []
        for asset in pending:
            source = Path(temporary) / asset['name']
            digest = sha256(source)
            if source.stat().st_size != asset['size']:
                raise ValueError(f"Release size mismatch: {asset['name']}")
            expected = asset_digest(asset)
            if digest != expected:
                raise ValueError(f"Release SHA-256 mismatch: {asset['name']}")
            package = read_package(source)
            if package.addon_id in ('.', '..'):
                raise ValueError(f'Invalid add-on ID: {package.addon_id}')
            destination = Path(package.addon_id) / package.filename
            if destination.is_file() and sha256(destination) == digest:
                print(f'Unchanged: {destination}')
                continue
            replacements.append((source, destination))
        for source, destination in replacements:
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f'Updating {destination} from Release')
            shutil.move(str(source), destination)
            changed = True
    return changed


def main():
    sources = Path('sources.txt')
    if not sources.exists():
        raise FileNotFoundError('sources.txt not found')
    failures = []
    changed = False
    for line in sources.read_text(encoding='utf-8').splitlines():
        repo = line.strip()
        if not repo or repo.startswith('#'):
            continue
        try:
            changed = download_release(repo) or changed
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            print(f'Error processing {repo}: {error}')
            failures.append(repo)
    if failures:
        raise RuntimeError(f"Failed to update: {', '.join(failures)}")
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as destination:
            destination.write(f'changed={str(changed).lower()}\n')
    print('Packages updated' if changed else 'No package changes; keeping the repository untouched')
    return changed


if __name__ == '__main__':
    main()
