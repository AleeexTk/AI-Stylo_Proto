import sys
import os
sys.path.append(os.getcwd())

try:
    from ai_stylo.core.database import init_db
    print("Attempting init_db...")
    init_db()
    print("Database initialized successfully!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
