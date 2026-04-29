import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"


def _normalized_database_url():
    if not DATABASE_URL:
        return None
    # Alcuni provider usano postgres://, psycopg2 preferisce postgresql://
    if DATABASE_URL.startswith("postgres://"):
        return "postgresql://" + DATABASE_URL[len("postgres://"):]
    return DATABASE_URL


def using_postgres() -> bool:
    return bool(_normalized_database_url())


def get_connection():
    if using_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor

        return psycopg2.connect(
            _normalized_database_url(),
            cursor_factory=RealDictCursor,
            sslmode="require",
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetchone(cursor):
    return cursor.fetchone()


def _execute(conn, query: str, params=()):
    if using_postgres():
        query = query.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(query, params)
    return cur


def init_db() -> None:
    with get_connection() as conn:
        if using_postgres():
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_premium INTEGER DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    profile TEXT NOT NULL,
                    txt_path TEXT,
                    pdf_path TEXT,
                    docx_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                cur.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
            except Exception:
                conn.rollback()
            conn.commit()
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_premium INTEGER DEFAULT 0
                )
                """
            )
            try:
                conn.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
            except Exception:
                pass
            conn.execute(
                """
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
                """
            )
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


def create_user(full_name: str, email: str, password: str) -> Optional[int]:
    password_hash = make_password_hash(password)
    try:
        with get_connection() as conn:
            if using_postgres():
                cur = _execute(
                    conn,
                    """
                    INSERT INTO users (full_name, email, password_hash)
                    VALUES (?, ?, ?)
                    RETURNING id
                    """,
                    (full_name.strip(), email.strip().lower(), password_hash),
                )
                row = cur.fetchone()
                conn.commit()
                return int(row["id"])
            else:
                cur = conn.execute(
                    "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                    (full_name.strip(), email.strip().lower(), password_hash),
                )
                conn.commit()
                return int(cur.lastrowid)
    except Exception:
        return None


def get_user_by_email(email: str):
    with get_connection() as conn:
        cur = _execute(
            conn,
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        )
        return cur.fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()


def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def save_report_record(user_id: int, profile: str, txt_path: str, pdf_path: str, docx_path: str) -> int:
    with get_connection() as conn:
        if using_postgres():
            cur = _execute(
                conn,
                """
                INSERT INTO reports (user_id, profile, txt_path, pdf_path, docx_path)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (user_id, profile, txt_path, pdf_path, docx_path),
            )
            row = cur.fetchone()
            conn.commit()
            return int(row["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO reports (user_id, profile, txt_path, pdf_path, docx_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, profile, txt_path, pdf_path, docx_path),
            )
            conn.commit()
            return int(cur.lastrowid)


def list_reports_for_user(user_id: int):
    with get_connection() as conn:
        cur = _execute(
            conn,
            """
            SELECT id, profile, txt_path, pdf_path, docx_path, created_at
            FROM reports
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        )
        return cur.fetchall()


def count_reports_for_user(user_id: int) -> int:
    with get_connection() as conn:
        cur = _execute(
            conn,
            "SELECT COUNT(*) AS total FROM reports WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["total"]) if row else 0


def set_user_premium(user_id: int, value: int):
    with get_connection() as conn:
        _execute(
            conn,
            "UPDATE users SET is_premium = ? WHERE id = ?",
            (1 if int(value) == 1 else 0, user_id),
        )
        conn.commit()


def is_user_premium(user_id: int) -> bool:
    with get_connection() as conn:
        cur = _execute(
            conn,
            "SELECT COALESCE(is_premium, 0) AS is_premium FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return bool(row and int(row["is_premium"]) == 1)


def get_all_users():
    with get_connection() as conn:
        cur = _execute(
            conn,
            """
            SELECT
                users.id,
                users.full_name,
                users.email,
                COALESCE(users.is_premium, 0) AS is_premium,
                COUNT(reports.id) AS report_count
            FROM users
            LEFT JOIN reports ON reports.user_id = users.id
            GROUP BY users.id, users.full_name, users.email, users.is_premium
            ORDER BY users.id DESC
            """,
        )
        rows = cur.fetchall()

    return [
        {
            "id": int(row["id"]),
            "name": row["full_name"],
            "email": row["email"],
            "report_count": int(row["report_count"]),
            "is_premium": int(row["is_premium"]) == 1,
            "plan": "Premium" if int(row["is_premium"]) == 1 else "Free",
        }
        for row in rows
    ]
