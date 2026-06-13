# save as check_db.py in medibot/ folder
import sqlite3
from pathlib import Path

# Check path 1 — relative
p1 = Path("data/db/mediassist.db")
print(f"Path 1 exists: {p1.exists()} | {p1.absolute()}")

# Check path 2 — next to sql_chain.py
p2 = Path(__file__).parent / "mediassist.db" if False else Path("data/db/mediassist.db")
print(f"Path 2 exists: {p2.exists()}")

# List what's actually in backend/sql_rag/
sql_dir = Path("backend/sql_rag")
print(f"\nFiles in backend/sql_rag/:")
for f in sql_dir.iterdir():
    print(f"  {f.name}")

# Try opening it
try:
    conn = sqlite3.connect(p1)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTables found: {tables}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")