import os

def final_sync():
    print("Starting final sync...")
    replacements = {
        "backend.database": "backend.db_manager",
        "backend.schemas": "backend.models",
        "import config": "from backend.core import config",
        "from database import": "from backend.db_manager import",
        "from models import": "from backend.models import",
        "from workers import": "from backend.workers import",
        "from services import": "from backend.services import",
        "from core import": "from backend.core import"
    }
    
    for root, dirs, files in os.walk("backend"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = content
                for old, new in replacements.items():
                    # Special check to avoid backend.backend.
                    if old in new_content:
                        # If replacing 'database' with 'backend.db_manager', 
                        # make sure we don't accidentally get 'backend.backend.db_manager'
                        if new.startswith("backend.") and f"backend.{old}" in new_content:
                            # If it already had backend. prefix, just update the suffix
                            # Example: backend.database -> backend.db_manager
                            # We'll do a direct string replace for the specific case
                            if old == "backend.database":
                                new_content = new_content.replace(old, new)
                            # skip others that are handled by the core mapping
                        else:
                            new_content = new_content.replace(old, new)
                
                # Cleanup potential double prefixes
                new_content = new_content.replace("from backend.backend.", "from backend.")
                new_content = new_content.replace("import backend.backend.", "import backend.")
                
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Synced: {path}")

if __name__ == "__main__":
    final_sync()
