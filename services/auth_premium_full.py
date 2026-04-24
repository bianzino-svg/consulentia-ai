# AUTH SERVICE WITH PREMIUM

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "consulentia.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def ensure_tables():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        is_premium INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def count_reports_for_user(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reports WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def set_user_premium(user_id, value):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = ? WHERE id = ?", (value, user_id))
    conn.commit()
    conn.close()


def is_user_premium(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == 1


def get_all_users():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, full_name, email, is_premium FROM users")
    users = cursor.fetchall()

    result = []
    for u in users:
        count = count_reports_for_user(u[0])
        result.append({
            "id": u[0],
            "name": u[1],
            "email": u[2],
            "report_count": count,
            "is_premium": u[3] == 1
        })

    conn.close()
    return result
