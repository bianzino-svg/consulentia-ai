import hashlib
import os
import secrets
import sqlite3
import string
from pathlib import Path
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"

def _normalized_database_url():
    if not DATABASE_URL:
        return None
    if DATABASE_URL.startswith("postgres://"):
        return "postgresql://" + DATABASE_URL[len("postgres://"):]
    return DATABASE_URL

def using_postgres() -> bool:
    return bool(_normalized_database_url())

def get_connection():
    if using_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(_normalized_database_url(), cursor_factory=RealDictCursor, sslmode="require")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _execute(conn, query: str, params=()):
    if using_postgres():
        query = query.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(query, params)
    return cur

def generate_access_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "CONS-" + "".join(secrets.choice(alphabet) for _ in range(6))

def init_db() -> None:
    with get_connection() as conn:
        if using_postgres():
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_premium INTEGER DEFAULT 0,
                    access_code TEXT,
                    access_status TEXT DEFAULT 'pending'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    profile TEXT NOT NULL,
                    txt_path TEXT,
                    pdf_path TEXT,
                    docx_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            for sql in [
                "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN access_code TEXT",
                "ALTER TABLE users ADD COLUMN access_status TEXT DEFAULT 'pending'",
            ]:
                try:
                    cur.execute(sql); conn.commit()
                except Exception:
                    conn.rollback()
            conn.commit()
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_premium INTEGER DEFAULT 0,
                    access_code TEXT,
                    access_status TEXT DEFAULT 'pending'
                )
            """)
            for sql in [
                "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN access_code TEXT",
                "ALTER TABLE users ADD COLUMN access_status TEXT DEFAULT 'pending'",
            ]:
                try: conn.execute(sql)
                except Exception: pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    profile TEXT NOT NULL,
                    txt_path TEXT,
                    pdf_path TEXT,
                    docx_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            conn.commit()

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

def make_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    return f"{salt}${_hash_password(password, salt)}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    return _hash_password(password, salt) == digest

def create_user(full_name: str, email: str, password: str, access_code: Optional[str] = None, access_status: str = "active") -> Optional[int]:
    password_hash = make_password_hash(password)
    code = access_code or generate_access_code()
    try:
        with get_connection() as conn:
            if using_postgres():
                cur = _execute(conn, "INSERT INTO users (full_name, email, password_hash, access_code, access_status) VALUES (?, ?, ?, ?, ?) RETURNING id",
                               (full_name.strip(), email.strip().lower(), password_hash, code, access_status))
                row = cur.fetchone(); conn.commit(); return int(row["id"])
            cur = conn.execute("INSERT INTO users (full_name, email, password_hash, access_code, access_status) VALUES (?, ?, ?, ?, ?)",
                               (full_name.strip(), email.strip().lower(), password_hash, code, access_status))
            conn.commit(); return int(cur.lastrowid)
    except Exception:
        return None

def request_access(full_name: str, email: str):
    clean_email = email.strip().lower()
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM users WHERE email = ?", (clean_email,))
        existing = cur.fetchone()
        if existing:
            return existing
    user_id = create_user(full_name or "Cliente", clean_email, secrets.token_urlsafe(16), generate_access_code(), "pending")
    return get_user_by_id(int(user_id)) if user_id else None

def get_user_by_email(email: str):
    with get_connection() as conn:
        return _execute(conn, "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()

def get_user_by_id(user_id: int):
    with get_connection() as conn:
        return _execute(conn, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user: return None
    if not verify_password(password, user["password_hash"]): return None
    return user

def authenticate_access_code(email: str, access_code: str):
    user = get_user_by_email(email)
    if not user: return None
    saved = str(user.get("access_code") or "").strip().upper()
    submitted = str(access_code or "").strip().upper()
    if not saved or saved != submitted: return None
    return user

def save_report_record(user_id: int, profile: str, txt_path: str, pdf_path: str, docx_path: str) -> int:
    with get_connection() as conn:
        if using_postgres():
            cur = _execute(conn, "INSERT INTO reports (user_id, profile, txt_path, pdf_path, docx_path) VALUES (?, ?, ?, ?, ?) RETURNING id",
                           (user_id, profile, txt_path, pdf_path, docx_path))
            row = cur.fetchone(); conn.commit(); return int(row["id"])
        cur = conn.execute("INSERT INTO reports (user_id, profile, txt_path, pdf_path, docx_path) VALUES (?, ?, ?, ?, ?)",
                           (user_id, profile, txt_path, pdf_path, docx_path))
        conn.commit(); return int(cur.lastrowid)

def list_reports_for_user(user_id: int):
    with get_connection() as conn:
        return _execute(conn, "SELECT id, profile, txt_path, pdf_path, docx_path, created_at FROM reports WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()

def count_reports_for_user(user_id: int) -> int:
    with get_connection() as conn:
        row = _execute(conn, "SELECT COUNT(*) AS total FROM reports WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["total"]) if row else 0

def set_user_premium(user_id: int, value: int):
    with get_connection() as conn:
        _execute(conn, "UPDATE users SET is_premium = ? WHERE id = ?", (1 if int(value) == 1 else 0, user_id)); conn.commit()

def set_user_active(user_id: int, value: int):
    with get_connection() as conn:
        _execute(conn, "UPDATE users SET access_status = ? WHERE id = ?", ("active" if int(value) == 1 else "pending", user_id)); conn.commit()

def regenerate_access_code(user_id: int) -> str:
    new_code = generate_access_code()
    with get_connection() as conn:
        _execute(conn, "UPDATE users SET access_code = ? WHERE id = ?", (new_code, user_id)); conn.commit()
    return new_code

def is_user_premium(user_id: int) -> bool:
    with get_connection() as conn:
        row = _execute(conn, "SELECT COALESCE(is_premium, 0) AS is_premium FROM users WHERE id = ?", (user_id,)).fetchone()
        return bool(row and int(row["is_premium"]) == 1)

def get_all_users():
    with get_connection() as conn:
        rows = _execute(conn, """
            SELECT users.id, users.full_name, users.email,
                   COALESCE(users.is_premium, 0) AS is_premium,
                   COALESCE(users.access_code, '') AS access_code,
                   COALESCE(users.access_status, 'pending') AS access_status,
                   COUNT(reports.id) AS report_count
            FROM users
            LEFT JOIN reports ON reports.user_id = users.id
            GROUP BY users.id, users.full_name, users.email, users.is_premium, users.access_code, users.access_status
            ORDER BY users.id DESC
        """).fetchall()
    return [{
        "id": int(row["id"]),
        "name": row["full_name"],
        "email": row["email"],
        "report_count": int(row["report_count"]),
        "is_premium": int(row["is_premium"]) == 1,
        "plan": "Premium" if int(row["is_premium"]) == 1 else "Free",
        "access_code": row["access_code"],
        "access_status": row["access_status"],
    } for row in rows]
