"""Read package metadata and keep Kodi-specific VFS builds separate."""

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


STANDARD_PLATFORMS = (
    'android-aarch64', 'android-armv7', 'linux-aarch64', 'linux-armv7',
    'linux-i686', 'linux-x86_64', 'windows-i686', 'windows-x86_64',
    'osx-x86_64', 'osx-arm64', 'ios-arm64',
)
KODI_RELEASES = {
    'Omega': ('21.0.0', '21.90.0'),
    'Piers': ('21.90.1', '22.90.0'),
}


def get_platform_from_filename(filename):
    return next((p for p in STANDARD_PLATFORMS if filename.endswith(f'-{p}.zip')), 'all')


@dataclass
class Package:
    path: Path
    root: ET.Element
    manifest: str
    platform: str
    codename: str | None

    @property
    def addon_id(self):
        return self.root.attrib['id']

    @property
    def version(self):
        return self.root.attrib['version']

    @property
    def filename(self):
        parts = [self.addon_id, self.version]
        if self.codename:
            parts.append(self.codename)
        if self.platform != 'all':
            parts.append(self.platform)
        return '-'.join(parts) + '.zip'


def read_package(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        manifests = [n for n in archive.namelist() if n.endswith('/addon.xml') and n.count('/') == 1]
        if len(manifests) != 1:
            raise ValueError(f'{path}: expected one top-level addon.xml')
        manifest = manifests[0]
        root = ET.fromstring(archive.read(manifest))
    if root.tag != 'addon' or not root.get('id') or not root.get('version'):
        raise ValueError(f'{path}: missing add-on ID/version')
    if manifest != f"{root.get('id')}/addon.xml":
        raise ValueError(f'{path}: add-on directory does not match its ID')
    platform = get_platform_from_filename(path.name)
    codename = None
    if root.get('id') == 'vfs.stream.fast':
        if platform == 'all':
            raise ValueError(f'{path}: missing VFS platform')
        match = re.fullmatch(
            rf"{re.escape(root.get('id'))}-{re.escape(root.get('version'))}"
            rf"(?:-(Omega|Piers))?-{re.escape(platform)}\.zip", path.name)
        if not match:
            raise ValueError(f'{path}: unrecognized VFS package name')
        # Releases before the dual build used Omega and had no codename.
        codename = match.group(1) or 'Omega'
    return Package(path, root, manifest, platform, codename)


def version_key(version):
    match = re.fullmatch(r'(\d+(?:\.\d+)*)(.*)', version)
    if not match:
        raise ValueError(f'Unsupported version: {version}')
    numbers = tuple(map(int, match.group(1).split('.')))
    suffix = match.group(2).lower()
    return (numbers + (0,) * max(0, 8 - len(numbers)), not bool(suffix), suffix)


def extract_assets(package, directory):
    assets = {'icon.png', 'icon.jpg', 'fanart.jpg', 'icon.gif', 'fanart.png'}
    for node in package.root.findall("extension[@point='xbmc.addon.metadata']/assets/*"):
        if node.text:
            assets.add(node.text.strip())
    with zipfile.ZipFile(package.path) as archive:
        for asset in assets:
            relative = Path(asset.replace('\\', '/'))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            member = f'{package.addon_id}/{relative.as_posix()}'
            if member in archive.namelist():
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))


def vfs_entries(directory):
    """Use each ZIP's own XML; never borrow an Omega manifest for Piers."""
    directory = Path(directory)
    packages = [read_package(path) for path in sorted(directory.glob('*.zip'))]
    result = {name: [] for name in KODI_RELEASES}
    for codename, (minimum, maximum) in KODI_RELEASES.items():
        candidates = [p for p in packages if p.codename == codename]
        if not candidates:
            continue
        latest = max(version_key(p.version) for p in candidates)
        selected = {}
        for package in candidates:
            if version_key(package.version) != latest:
                continue
            # Prefer the explicitly named build over an old ZIP at the same version.
            previous = selected.get(package.platform)
            if previous is None or f'-{codename}-' in package.path.name:
                selected[package.platform] = package

        # CoreELEC ng may report only "linux". Keep its fallback after exact
        # architectures: Kodi keeps the first matching entry at equal versions.
        ordered = sorted(selected, key=lambda p: (p == 'linux-armv7', p))
        for platform in ordered:
            package = selected[platform]
            root = package.root
            metadata = root.find("extension[@point='xbmc.addon.metadata']")
            if metadata is None:
                raise ValueError(f'{package.path}: missing metadata')
            for tag, value in (('platform', 'linux-armv7 linux' if platform == 'linux-armv7' else platform),
                               ('path', f'{package.addon_id}/{package.path.name}')):
                for old in metadata.findall(tag):
                    metadata.remove(old)
                ET.SubElement(metadata, tag).text = value
            requires = root.find('requires')
            if requires is None:
                requires = ET.SubElement(root, 'requires')
            dependency = requires.find("import[@addon='xbmc.addon']")
            if dependency is None:
                dependency = ET.SubElement(requires, 'import', addon='xbmc.addon')
            dependency.set('version', minimum)
            dependency.set('maxversion', maximum)
            result[codename].append(ET.tostring(root, encoding='unicode'))
        extract_assets(selected[ordered[0]], directory)
    return result
