"""Слой доступа к SQLite (клиника «Дентал+»)."""
import pathlib
import sqlite3

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "dental.db"
MYSQL = {"database": str(DB_PATH)}   # имя сохранено для совместимости с backup.py


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    with connect() as c:
        return c.execute(sql, params).fetchall()


def execute(sql, params=()):
    with connect() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid