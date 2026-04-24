import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'app.db'


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
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
            )
            """
        )
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
    return hashlib.sha256(f'{salt}:{password}'.encode('utf-8')).hexdigest()


def make_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    return f'{salt}${_hash_password(password, salt)}'


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split('$', 1)
    except ValueError:
        return False
    return _hash_password(password, salt) == digest


def create_user(full_name: str, email: str, password: str) -> Optional[int]:
    password_hash = make_password_hash(password)
    try:
        with get_connection() as conn:
            cur = conn.execute(
                'INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)',
                (full_name.strip(), email.strip().lower(), password_hash),
            )
            conn.commit()
            return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def get_user_by_email(email: str):
    with get_connection() as conn:
        return conn.execute(
            'SELECT * FROM users WHERE email = ?',
            (email.strip().lower(),),
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            'SELECT * FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()


def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user['password_hash']):
        return None
    return user


def save_report_record(user_id: int, profile: str, txt_path: str, pdf_path: str, docx_path: str) -> int:
    with get_connection() as conn:
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
        return conn.execute(
            """
            SELECT id, profile, txt_path, pdf_path, docx_path, created_at
            FROM reports
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()


def count_reports_for_user(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS total FROM reports WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        return int(row['total']) if row else 0


def get_all_users():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                users.id,
                users.full_name,
                users.email,
                COUNT(reports.id) AS report_count
            FROM users
            LEFT JOIN reports ON reports.user_id = users.id
            GROUP BY users.id, users.full_name, users.email
            ORDER BY users.id DESC
            """
        ).fetchall()

    return [
        {
            'id': int(row['id']),
            'name': row['full_name'],
            'email': row['email'],
            'report_count': int(row['report_count']),
            'plan': 'Free',
        }
        for row in rows
    ]
def set_user_premium(user_id: int, value: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_premium = ? WHERE id = ?",
            (1 if int(value) == 1 else 0, user_id),
        )
        conn.commit()


def is_user_premium(user_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(is_premium, 0) as is_premium FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return bool(row and int(row["is_premium"]) == 1)
