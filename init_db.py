import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCHEMA_FILE = BASE / "sql" / "01_schema_sqlite.sql"
DB_PATH = BASE / "dental.db"

con = sqlite3.connect(DB_PATH)
con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
con.commit()
con.close()
print(f"БД создана: {DB_PATH}")