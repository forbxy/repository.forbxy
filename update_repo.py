import os
import requests
import json
import zipfile
import re
import shutil
import subprocess

# Map github release asset names to kodi platform strings
PLATFORM_MAPPING = {
    'android-arm64-v8a': 'android-aarch64',
    'android-armeabi-v7a': 'android-armv7',
    'linux-arm32': 'linux-armv7',
    'linux-arm64': 'linux-aarch64',
    'linux-x64': 'linux-x86_64',
    'linux-x86': 'linux-i686',
    'windows-x64': 'windows-x86_64',
    'windows-x86': 'windows-i686',
    'osx-x86_64': 'osx-x86_64',
    'osx-arm64': 'osx-arm64',
    'ios-arm64': 'ios-arm64'
}

STANDARD_PLATFORMS = list(PLATFORM_MAPPING.values())

def get_platform_from_filename(filename):
    """
    Extracts platform string from filename based on known patterns.
    Returns 'all' for generic python addons or the specific kodi platform string.
    """
    # Check for platform specific binary addons
    for pattern, platform in PLATFORM_MAPPING.items():
        if pattern in filename:
            return platform
            
    # Check if filename already contains standard platform string
    for platform in STANDARD_PLATFORMS:
         if platform in filename:
             return platform

    # Default to generic python addon
    return 'all'

def download_release(repo_url):
    try:
        repo_name = repo_url.replace("https://github.com/", "").strip()
        print(f"Checking {repo_name}...")

        # Use GH CLI to get latest release info
        cmd = f'gh release view --repo {repo_name} --json tagName,assets'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error checking release for {repo_name}: {result.stderr}")
            return

        data = json.loads(result.stdout)
        tag_name = data['tagName']
        assets = data['assets']
        
        # Clean version number (remove 'v' prefix)
        version = tag_name.lstrip('v')
        
        print(f"Latest version: {version}")

        # Create temp directory
        if not os.path.exists("temp_dl"):
            os.makedirs("temp_dl")

        # Download assets
        cmd = f'gh release download {tag_name} --repo {repo_name} --pattern "*.zip" --dir temp_dl'
        subprocess.run(cmd, shell=True, check=True)

        for asset in assets:
            filename = asset['name']
            if not filename.endswith('.zip'):
                continue
                
            file_path = os.path.join("temp_dl", filename)
            if not os.path.exists(file_path):
                continue

            # Identify Addon ID from zip content
            addon_id = None
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('addon.xml') and name.count('/') == 1:
                            with zf.open(name) as f:
                                content = f.read().decode('utf-8')
                                match = re.search(r'id="([^"]+)"', content)
                                if match:
                                    addon_id = match.group(1)
                                    break
            except Exception as e:
                print(f"Error reading zip {filename}: {e}")
                continue

            if not addon_id:
                print(f"Could not find addon id in {filename}")
                continue

            # Determine platform and renaming strategy
            platform = get_platform_from_filename(filename)
            
            # Create addon directory
            dest_dir = os.path.join(".", addon_id)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)

            # Construct new filename
            # For binary addons with specific platforms, we use the specific format
            # For generic addons, we use the standard format
            if platform != 'all':
                new_filename = f"{addon_id}-{version}-{platform}.zip"
            else:
                new_filename = f"{addon_id}-{version}.zip"

            dest_path = os.path.join(dest_dir, new_filename)
            
            # Custom handling for existing addon.xml to inject platform info if needed
            # This logic will be handled by a modified generate_repo.py
            # Here we just place the file
            
            # Logic: If platform specific, we need to create a marker file or 
            # ensure generate_repo can detect it.
            # We will rely on filename parsing in generate_repo.py

            print(f"Moving {filename} to {dest_path}")
            shutil.move(file_path, dest_path)
            
            # Clean up old versions?
            # Ideally yes, but tricky to distinguish platform files vs versions. 
            # For now, let's keep it simple and maybe cleanup later.

        # Clean up temp
        shutil.rmtree("temp_dl")

    except Exception as e:
        print(f"Error processing {repo_url}: {e}")

def main():
    if not os.path.exists('sources.txt'):
        print("sources.txt not found")
        return

    with open('sources.txt', 'r') as f:
        repos = [line.strip() for line in f if line.strip()]

    for repo in repos:
        download_release(repo)

if __name__ == "__main__":
    main()