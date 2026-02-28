import os
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import re

def get_addon_info(addon_xml_path):
    try:
        tree = ET.parse(addon_xml_path)
        root = tree.getroot()
        if root.tag == 'addon':
            addon_id = root.get('id')
            version = root.get('version')
            return addon_id, version, root
    except Exception as e:
        print(f"Error parsing {addon_xml_path}: {e}")
    return None, None, None

def create_zip(source_dir, output_zip):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Get the parent directory name to ensure consistent structure inside zip
        parent_dir = os.path.dirname(os.path.abspath(source_dir))
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".zip") or file.endswith(".pyc") or file == "generate_repo.py" or file.startswith("."):
                    continue
                file_path = os.path.join(root, file)
                # Calculate relative path from the parent of source_dir
                # If source_dir is ./plugin.video.foo, zip should contain plugin.video.foo/addon.xml
                archive_name = os.path.relpath(file_path, parent_dir)
                zf.write(file_path, archive_name)
    print(f"Created {output_zip}")

def generate_repo():
    addons_xml = u"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<addons>\n"
    
    # Process subdirectories
    for item in os.listdir("."):
        if os.path.isdir(item) and item != "." and item != ".." and not item.startswith("."):
            
            # Check for binary platform specific zips first
            platform_zips = []
            for file in os.listdir(item):
                if file.endswith(".zip"):
                    # pattern: ID-Version-Platform.zip
                    # but standard is ID-Version.zip
                    # we look for the 3rd component
                    parts = file[:-4].split('-') # remove .zip
                    if len(parts) > 2:
                        # Simple heuristic: if filename contains platform keywords
                        # This relies on update_repo.py naming convention
                        platform = None
                        if 'android' in file: platform = 'android'
                        elif 'windows' in file: platform = 'windows'
                        elif 'linux' in file: platform = 'linux'
                        elif 'osx' in file: platform = 'osx'
                        elif 'ios' in file: platform = 'ios'
                        
                        if platform:
                             platform_zips.append(file)

            # Standard processing
            addon_xml_path = os.path.join(item, "addon.xml")
            addon_xml_content = None

            # If no addon.xml but we have zips (downloaded from sources), try to extract one
            if len(os.listdir(item)) > 0:
                 # Try to find a zip to extract addon.xml and assets from
                 zips = [f for f in os.listdir(item) if f.endswith('.zip')]
                 if zips:
                     # Sort zips by version, assuming format name-version.zip
                     try:
                        # Extract the version part. This logic could be fragile.
                        # We use LooseVersion-like sorting or just sort by name (usually works for version numbers with same length)
                        # A better way is to try to parse versions
                        def get_version_key(filename):
                            # Remove .zip
                            base = filename[:-4]
                            
                            # Try to find version using regex (e.g., 1.2.3 or 1.2.3.4)
                            # Matches version numbers surrounded by - or end of string
                            import re
                            # This regex looks for digits.digits... possibly followed by more .digits
                            # It tries to find the version segment in the filename
                            # We assume the version is the first segment that looks like X.Y.Z
                            # surrounded by hyphens or end of string
                            # Typical formats: addon.id-1.2.3.zip, addon.id-1.2.3-matrix.zip
                            
                            parts = base.split('-')
                            # Iterate parts to find the one that looks like a version
                            for part in parts:
                                if re.match(r'^\d+(\.\d+)+[a-z0-9]*$', part):
                                    try:
                                        # Convert to tuple of ints for proper comparison
                                        # e.g. 1.10 > 1.2
                                        # Handle suffixes like 1.2.3a
                                        v_clean = re.sub(r'[^0-9\.]', '', part)
                                        return [int(x) for x in v_clean.split('.') if x]
                                    except ValueError:
                                        pass
                            
                            return filename

                        # Sort descending, so highest version is first
                        zips.sort(key=get_version_key, reverse=True) 
                     except Exception:
                        zips.sort(reverse=True) # Fallback to string sort

                     # Pick the latest zip
                     target_zip = zips[0]
                     
                     try:
                         with zipfile.ZipFile(os.path.join(item, target_zip), 'r') as zf:
                             root_folder = None
                             for name in zf.namelist():
                                 if name.endswith('addon.xml') and name.count('/') == 1:
                                     root_folder = name[:-9] # remove addon.xml
                                     break
                                     
                             if root_folder:
                                 # Read addon.xml content directly from zip
                                 try:
                                     with zf.open(root_folder + "addon.xml") as source:
                                         addon_xml_content = source.read().decode('utf-8')
                                 except KeyError:
                                     pass 
                                         
                                 # Extract assets (icon.png, fanart.jpg, etc) based on addon.xml content
                                 # Parse addon.xml to find assets
                                 assets_to_extract = set(['icon.png', 'fanart.jpg', 'icon.gif', 'fanart.png'])
                                 
                                 try:
                                     if addon_xml_content:
                                        try:
                                            root_xml = ET.fromstring(addon_xml_content)
                                            
                                            # Handle standard assets tag
                                            for extension in root_xml.findall("extension"):
                                                # Also check if it's metadata
                                                point = extension.get("point")
                                                if point == "xbmc.addon.metadata":
                                                    # Look for <assets>
                                                    assets_elem = extension.find("assets")
                                                    if assets_elem is not None:
                                                        for child in assets_elem:
                                                            if child.text:
                                                                assets_to_extract.add(child.text.strip())
                                        except ET.ParseError:
                                            # Fallback: simple text parsing if XML is malformed or weirdly encoded
                                            if '<assets>' in addon_xml_content:
                                                assets_match = re.search(r'<assets>(.*?)</assets>', addon_xml_content, re.DOTALL)
                                                if assets_match:
                                                    inner = assets_match.group(1)
                                                    # Find all tags inside
                                                    tags = re.findall(r'<([^>]+)>([^<]+)</\1>', inner)
                                                    for tag, text in tags:
                                                        assets_to_extract.add(text.strip())

                                 except Exception as e:
                                     print(f"Error parsing assets XML: {e}")

                                 for asset in assets_to_extract:
                                     asset = asset.strip()
                                     if not asset: continue
                                     
                                     # Normalize path separators for zip lookup
                                     asset_norm = asset.replace('\\', '/')
                                     
                                     # In zip: "plugin.video.foo/resources/image.jpg"
                                     asset_path_in_zip = root_folder + asset_norm
                                     
                                     # On disk: "plugin.video.foo/resources/image.jpg"
                                     # (relative to current working directory, item is the plugin folder)
                                     local_asset_path = os.path.join(item, asset_norm)
                                     
                                     try:
                                         if asset_path_in_zip in zf.namelist():
                                             # Ensure subdirectories exist
                                             os.makedirs(os.path.dirname(local_asset_path), exist_ok=True)
                                             
                                             with zf.open(asset_path_in_zip) as source, open(local_asset_path, "wb") as target:
                                                 target.write(source.read())
                                     except (KeyError, FileNotFoundError):
                                         pass
                     except Exception as e:
                         print(f"Error extracting from {target_zip}: {e}")

            if addon_xml_content:
                # Parse XML content from memory instead of file
                try:
                    root = ET.fromstring(addon_xml_content)
                    addon_id = root.get('id')
                    version = root.get('version')
                except ET.ParseError:
                    addon_id = None
                    version = None
                    # Try regex fallback on content
                    id_match = re.search(r'id="([^"]+)"', addon_xml_content)
                    ver_match = re.search(r'version="([^"]+)"', addon_xml_content)
                    if id_match: addon_id = id_match.group(1)
                    if ver_match: version = ver_match.group(1)

                if addon_id and version:
                    
                    # If we found platform specific zips, we need to generate multiple entries
                    # or inject platform tags
                    processed_platforms = False
                    
                    if platform_zips:
                        # We have binary platform zips. We need to duplicate the xml entry for each platform
                        # and inject <platform> and <path> tags
                        
                        base_xml_content = ET.tostring(root, encoding='unicode', method='xml')
                        # Remove ns0: prefixes if ElementTree added them
                        base_xml_content = base_xml_content.replace('ns0:', '').replace(':ns0', '')
                        
                        # Parse regex to matching platform zips more accurately
                        # update_repo.py naming: addon_id-version-platform.zip
                        for zip_file in platform_zips:
                            # Parse platform from filename: plugin.video.foo-1.0.0-windows-x86_64.zip
                            # We know the ID and Version.
                            prefix = f"{addon_id}-{version}-"
                            if zip_file.startswith(prefix):
                                platform_str = zip_file[len(prefix):-4] # remove prefix and .zip
                                
                                # Now modify the XML for this platform
                                # We'll do string manipulation for simplicity as ET can be tricky with namespaces/attributes
                                
                                # 1. Find the extension metadata block
                                metadata_pattern = r'(<extension point="xbmc\.addon\.metadata"[^>]*>)(.*?)(</extension>)'
                                match = re.search(metadata_pattern, base_xml_content, re.DOTALL)
                                
                                if match:
                                    start_tag = match.group(1)
                                    inner_content = match.group(2)
                                    end_tag = match.group(3)
                                    
                                    # Override/Add platform
                                    # Remove existing platform tag if any
                                    inner_content = re.sub(r'<platform>.*?</platform>', '', inner_content)
                                    # Add new platform tag
                                    inner_content += f'\n            <platform>{platform_str}</platform>'
                                    # Add path tag
                                    # Note: path should be relative to datadir. 
                                    # datadir is repo/master/. 
                                    # file is at repo/plugin.video.foo/file.zip
                                    inner_content += f'\n            <path>{item}/{zip_file}</path>\n    '
                                    
                                    new_entry = base_xml_content.replace(match.group(0), f"{start_tag}{inner_content}{end_tag}")
                                    addons_xml += new_entry.strip() + "\n"
                                    processed_platforms = True
                    
                    # If it wasn't a recognized binary platform set updates, or just a regular addon
                    if not processed_platforms:
                        # Create zip if not exists (for locally developed addons)
                        zip_name = f"{addon_id}-{version}.zip"
                        zip_path = os.path.join(item, zip_name)
                        if not os.path.exists(zip_path) and not any(f.endswith('.zip') for f in os.listdir(item)):
                             create_zip(item, zip_path)
                        
                        # Add to XML
                        if addon_xml_content:
                            content = addon_xml_content
                            lines = content.splitlines()
                            if lines[0].startswith("<?xml"):
                                content = "\n".join(lines[1:])
                            addons_xml += content.strip() + "\n"
    
    # Create repository.forbxy zip from current directory addon.xml
    if os.path.exists("addon.xml"):
        repo_addon_xml = "addon.xml"
        try:
            tree = ET.parse(repo_addon_xml)
            root = tree.getroot()
            repo_id = root.get('id')
            repo_version = root.get('version')
            
            if repo_id and repo_version:
                repo_zip_name = f"{repo_id}-{repo_version}.zip"
                # Ensure repo directory exists
                if not os.path.exists(repo_id):
                    os.makedirs(repo_id)
                repo_zip_path = os.path.join(repo_id, repo_zip_name)
                # Ensure the zip is also copied to root for flat index.html access
                root_zip_path = repo_zip_name
                
                print(f"Creating repository zip: {repo_zip_path}")
                with zipfile.ZipFile(repo_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                     zf.write("addon.xml", f"{repo_id}/addon.xml")
                     # Also include icon/fanart if they exist
                     for extra in ['icon.png', 'icon.jpg', 'fanart.jpg']:
                         if os.path.exists(extra):
                             zf.write(extra, f"{repo_id}/{extra}")
                             # Also copy to disk for direct access if needed
                             import shutil
                             shutil.copy2(extra, f"{repo_id}/{extra}")
                             
                # Copy zip to root for flat access
                import shutil
                shutil.copy2(repo_zip_path, root_zip_path)
                             
                # Also Add repo itself to addons.xml
                with open(repo_addon_xml, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.splitlines()
                    if lines[0].startswith("<?xml"):
                        content = "\n".join(lines[1:])
                    addons_xml += content.strip() + "\n"

        except Exception as e:
            print(f"Error packing repository addon: {e}")

    # Create repository.forbxy.ghproxy zip (Clone of repository.forbxy but with gh-proxy links)
    if os.path.exists("addon.xml"):
        try:
             # Parse original again
             with open("addon.xml", "r", encoding="utf-8") as f:
                 orig_xml_content = f.read()

             # Modify ID, Name, and Links
             proxy_xml_content = orig_xml_content.replace('id="repository.forbxy"', 'id="repository.forbxy.ghproxy"')
             proxy_xml_content = proxy_xml_content.replace('name="kodi forbxy Add-on repository"', 'name="kodi forbxy Add-on repository (GHProxy)"')
             
             # Prepend gh-proxy
             # Pattern: https://raw.githubusercontent.com
             proxy_xml_content = proxy_xml_content.replace('https://raw.githubusercontent.com', 'https://gh-proxy.org/https://raw.githubusercontent.com')
             
             # Extract verify info
             root = ET.fromstring(proxy_xml_content)
             repo_id = root.get('id')
             repo_version = root.get('version')
             
             if repo_id and repo_version:
                repo_zip_name = f"{repo_id}-{repo_version}.zip"
                # Ensure repo directory exists
                if not os.path.exists(repo_id):
                    os.makedirs(repo_id)
                
                # Write modified addon.xml temporarily
                temp_proxy_xml = f"{repo_id}/addon.xml"
                with open(temp_proxy_xml, "w", encoding="utf-8") as f:
                    f.write(proxy_xml_content)
                
                repo_zip_path = os.path.join(repo_id, repo_zip_name)
                print(f"Creating proxy repository zip: {repo_zip_path}")
                
                with zipfile.ZipFile(repo_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                     zf.write(temp_proxy_xml, f"{repo_id}/addon.xml")
                     
                     # Also include icon/fanart if they exist
                     for extra in ['icon.png', 'icon.jpg', 'fanart.jpg']:
                         if os.path.exists(extra):
                             zf.write(extra, f"{repo_id}/{extra}")
                             # Also copy to disk for direct access if needed
                             import shutil
                             if not os.path.exists(f"{repo_id}/{extra}"):
                                 shutil.copy2(extra, f"{repo_id}/{extra}")
                
                # Copy zip to root for flat access
                root_zip_path = repo_zip_name
                import shutil
                shutil.copy2(repo_zip_path, root_zip_path)

                # Clean up temp xml
                if os.path.exists(temp_proxy_xml):
                    os.remove(temp_proxy_xml)
                             
                # Add proxy repo to addons.xml list
                lines = proxy_xml_content.splitlines()
                if lines[0].startswith("<?xml"):
                    proxy_xml_content = "\n".join(lines[1:])
                addons_xml += proxy_xml_content.strip() + "\n"
        except Exception as e:
            print(f"Error processing proxy repository: {e}")

    addons_xml += "</addons>\n"
    
    # Write addons.xml first
    with open("addons.xml", "w", encoding="utf-8") as f:
        f.write(addons_xml)
    
    # Calculate MD5 from the file content on disk to ensure consistency
    hash_md5 = hashlib.md5()
    with open("addons.xml", "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    
    md5 = hash_md5.hexdigest()
    
    with open("addons.xml.md5", "w", encoding="utf-8") as f:
        f.write(md5)
        
    print(f"Generated addons.xml (MD5: {md5})")
    
    # Generate index.html for Kodi File Manager Source
    # Lists only the repository zip files for easy installation
    # User requested a friendly page with descriptions (Bilingual)
    index_html = """<!DOCTYPE html>
<html>
<head>
<title>Forbxy Kodi Repository</title>
<meta charset="utf-8">
</head>
<body>
<h1>Forbxy Kodi Repository</h1>
<p>Forbxy 的 Kodi 插件仓库 / Kodi add-ons developed by Forbxy.</p>
<hr>
<p>
<b>repository.forbxy-*.zip</b>: 原始版本，使用 GitHub Raw 链接。<br>
Original version, uses GitHub Raw links.
</p>
<p>
<b>repository.forbxy.ghproxy-*.zip</b>: 加速版本，使用 gh-proxy.com 代理链接（<b>中国大陆用户推荐 / Recommended for users in China</b>）。<br>
Proxy version, uses gh-proxy.com links.
</p>
<hr>
<pre>
"""
    
    # Find all repository zips we just created (now also in root)
    repo_zips = []
    
    # We look for the zips in the root directory
    for f in os.listdir("."):
        if f.endswith(".zip") and f.startswith("repository.forbxy"):
            repo_zips.append(f)
            
    # Sort them to be nice
    repo_zips.sort()
                
    for zip_path in repo_zips:
        filename = os.path.basename(zip_path)
        size_bytes = os.path.getsize(zip_path)
        # Format: <a href="filename">filename</a>        Size
        # Using <pre> block for alignment
        index_html += f'<a href="{filename}">{filename}</a>{" " * (50 - len(filename))}{size_bytes} bytes<br>\n'
        
    index_html += """</pre>
<hr>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    print("Generated index.html")

if __name__ == "__main__":
    generate_repo()