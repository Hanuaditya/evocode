import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "evocode.db")

def migrate():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE fix_attempts ADD COLUMN agent_logs TEXT;")
        print("Successfully added 'agent_logs' column to 'fix_attempts' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'agent_logs' already exists in 'fix_attempts'.")
        else:
            print(f"OperationalError: {e}")
            raise
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
