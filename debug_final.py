import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

print(f"Python Version: {sys.version}")
print(f"Project Root: {ROOT_DIR}")
print(f"sys.path: {sys.path[:3]}")

try:
    import backend.database as db
    print(f"backend.database location: {db.__file__}")
    from backend.database import MetadataDB
    print("MetadataDB imported successfully!")
except Exception as e:
    print(f"Import Error: {e}")
    import traceback
    traceback.print_exc()
