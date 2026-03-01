import sqlite3
import os
from pathlib import Path

def migrate():
    # Attempt to locate the database
    project_root = Path(__file__).resolve().parent
    db_path = project_root / "data" / "memory.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}, skipping migration.")
        return

    print(f"Migrating database: {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of columns to add with their default values
    cols_to_add = [
        ("gender", "TEXT DEFAULT 'male'"),
        ("body_type", "TEXT DEFAULT 'rectangular'"),
        ("measurements_json", "TEXT DEFAULT '{}'")
    ]
    
    for col_name, col_def in cols_to_add:
        try:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE user_profile ADD COLUMN {col_name} {col_def}")
            conn.commit()
            print(f"Column {col_name} added successfully.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding column {col_name}: {e}")

    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
