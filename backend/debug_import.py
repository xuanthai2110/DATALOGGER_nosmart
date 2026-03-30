import sys
import os

# Add backend to path (as done in run_polling.py)
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

print(f"Current Path: {os.getcwd()}")
print(f"File Path: {__file__}")
print(f"Backend Dir Added: {backend_dir}")
print(f"sys.path[0]: {sys.path[0]}")

try:
    import backend.db_manager
    print(f"Database module found at: {database.__file__}")
    from backend.db_manager import MetadataDB
    print("MetadataDB imported successfully")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
