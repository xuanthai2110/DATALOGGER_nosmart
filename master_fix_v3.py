import os
import re

def master_fix_v3():
    print("Starting master import fix V3 (Absolute Manager)...")
    # 1. Rename folder if needed (assuming rename already happened via mv)
    # But for safety, we'll process all .py files in backend/
    
    # 2. Replacements for everything, ensuring 'backend.' prefix
    pkgs = ["db_manager", "database", "models", "workers", "services", "core", "drivers", "communication", "api"]
    
    for root, dirs, files in os.walk("backend"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = content
                
                # Prepend backend. to top-level pkg imports
                for pkg in pkgs:
                    # from pkg -> from backend.db_manager (special handling for database -> db_manager)
                    target_pkg = "db_manager" if pkg == "database" else pkg
                    
                    # pattern: from [pkg] or from [pkg]. or import [pkg]
                    # BUT NOT if already backend.[target_pkg]
                    
                    # Replace 'from database' or 'from database.' or 'from models'
                    pattern_from = rf'\bfrom\s+({pkg})\b'
                    new_content = re.sub(pattern_from, rf'from backend.{target_pkg}', new_content)
                    
                    # Replace 'import database'
                    pattern_import = rf'\bimport\s+({pkg})\b'
                    new_content = re.sub(pattern_import, rf'import backend.{target_pkg}', new_content)
                
                # Double-check for circularities (manual fix for known ones if any)
                # Cleanup backend.backend.
                new_content = new_content.replace("backend.backend.", "backend.")
                
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Fixed: {path}")

if __name__ == "__main__":
    master_fix_v3()
