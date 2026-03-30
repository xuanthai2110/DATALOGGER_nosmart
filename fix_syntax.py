import os

def fix_syntax():
    print("Fixing double prefix syntax errors...")
    target = "from backend.core from backend.core import config"
    fixed = "from backend.core import config"
    
    for root, dirs, files in os.walk("backend"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if target in content:
                    new_content = content.replace(target, fixed)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Fixed syntax in: {path}")

if __name__ == "__main__":
    fix_syntax()
