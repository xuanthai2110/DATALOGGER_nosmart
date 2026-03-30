import os
import re

def master_fix():
    print("Starting master import fix V2 (Nuker)...")
    root_dir = "backend"
    
    # Packages to prepend with backend.
    pkgs = [
        "database", "models", "workers", "services", 
        "core", "drivers", "communication", "api", "schemas"
    ]
    
    # Regex to match 'from pkg' or 'import pkg' at start of line or after space
    # but NOT if already started with 'backend.'
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                if file == "__init__.py":
                    continue # Skip __init__ which often use local relative imports
                    
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = content
                for pkg in pkgs:
                    # Case 1: from pkg[...]
                    # Match 'from ' followed by pkg, NOT preceded by 'backend.'
                    pattern_from = rf'(?<!backend\.)\bfrom\s+({pkg})\b'
                    new_content = re.sub(pattern_from, r'from backend.\1', new_content)
                    
                    # Case 2: import pkg[...]
                    pattern_import = rf'(?<!backend\.)\bimport\s+({pkg})\b'
                    new_content = re.sub(pattern_import, r'import backend.\1', new_content)
                
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Fixed: {path}")

if __name__ == "__main__":
    master_fix()
