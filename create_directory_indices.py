import os

def create_directory_indices():
    # Get all directories in current path
    dirs = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.') and d != '__pycache__']
    dirs.sort()

    for d in dirs:
        # Check if it looks like an addon directory (has addon.xml or zip files)
        # We can be loose here and just generate index for all subdirectories just in case
        files = [f for f in os.listdir(d) if not f.startswith('.') and f != 'index.html' and f != '__pycache__']
        files.sort()
        
        # Simple HTML template compatible with Kodi HTTP dictionary scraping
        html = """<!DOCTYPE html>
<html>
<head>
<title>Index of /%s</title>
</head>
<body>
<h1>Index of /%s</h1>
<hr><pre>
""" % (d, d)
        
        # Add parent link
        html += '<a href="../">../</a>\n'
        
        for f in files:
            # Check if directory
            is_dir = os.path.isdir(os.path.join(d, f))
            display_name = f + "/" if is_dir else f
            
            # Simple alignment
            space_len = 50 - len(display_name)
            space = " " * space_len if space_len > 0 else " "
            
            # Get size for files
            if not is_dir:
                try:
                    size = os.path.getsize(os.path.join(d, f))
                except:
                    size = 0
                size_str = str(size)
            else:
                size_str = "-"
            
            html += f'<a href="{display_name}">{display_name}</a>{space}{size_str}\n'
            
        html += """</pre><hr></body>
</html>
"""
        
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
            print(f"Created index.html for {d}")

if __name__ == '__main__':
    create_directory_indices()
