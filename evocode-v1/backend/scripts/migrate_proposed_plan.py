"""
backend/scripts/migrate_proposed_plan.py

Adds proposed_plan (TEXT) and confidence_score (INTEGER) columns to issue_reports.
Safe to re-run — handles 'duplicate column name' gracefully.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "evocode.db")

def migrate():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for col, definition in [
        ("proposed_plan",    "TEXT"),
        ("confidence_score", "INTEGER"),
        ("requires_human",   "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE issue_reports ADD COLUMN {col} {definition};")
            print(f"  [OK] Added column: {col}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"  [SKIP] Column already exists: {col}")
            else:
                raise

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
