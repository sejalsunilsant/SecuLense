"""Local authentication and session store using SQLite."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
DB_FILE = ROOT / "data" / "local_auth.sqlite3"
PASSWORD_ROUNDS = 310_000
SESSION_HOURS = 12
COOKIE_NAME = "secu_session"


class AuthStore:
    def __init__(self, path: Path | str = DB_FILE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def user_count(self) -> int:
        with self.connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    @staticmethod
    def validate_credentials(username: str, password: str) -> tuple[str, bytes]:
        username = username.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
            raise ValueError("Username must be 3–32 characters: letters, numbers, dot, dash, or underscore.")
        if len(password) < 10 or len(password) > 256:
            raise ValueError("Password must be between 10 and 256 characters.")
        return username, password.encode("utf-8")

    def create_first_user(self, username: str, password: str) -> dict:
        username, password_bytes = self.validate_credentials(username, password)
        salt = secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, PASSWORD_ROUNDS)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise RuntimeError("Setup is already complete. Sign in with your existing account.")
            db.execute(
                "INSERT INTO users(username,password_salt,password_hash,created_at) VALUES(?,?,?,?)",
                (username, salt, hashed, datetime.now(timezone.utc).isoformat()),
            )
            row = db.execute("SELECT id,username FROM users WHERE username=?", (username,)).fetchone()
        return {"id": row["id"], "username": row["username"]}

    def create_user(self, username: str, password: str) -> dict:
        """Create an additional local dashboard account."""
        username, password_bytes = self.validate_credentials(username, password)
        salt = secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, PASSWORD_ROUNDS)
        try:
            with self.connect() as db:
                cursor = db.execute(
                    "INSERT INTO users(username,password_salt,password_hash,created_at) VALUES(?,?,?,?)",
                    (username, salt, hashed, datetime.now(timezone.utc).isoformat()),
                )
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("That username is already in use. Choose another one.") from exc
        return {"id": user_id, "username": username}

    def authenticate(self, username: str, password: str) -> dict | None:
        username = username.strip()[:32]
        with self.connect() as db:
            row = db.execute(
                "SELECT id,username,password_salt,password_hash FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if row is None:
            hashlib.pbkdf2_hmac("sha256", password.encode("utf-8")[:256], b"seculense-dummy-salt", PASSWORD_ROUNDS)
            return None
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8")[:256], row["password_salt"], PASSWORD_ROUNDS)
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"]}

    def create_session(self, user_id: int) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat()),
            )
        return token, expires.isoformat()

    def get_session_user(self, token: str | None) -> dict | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            row = db.execute("""
                SELECT users.id, users.username FROM sessions
                JOIN users ON users.id=sessions.user_id
                WHERE sessions.token_hash=? AND sessions.expires_at>?
            """, (token_hash, now)).fetchone()
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
        return {"id": row["id"], "username": row["username"]} if row else None

    def revoke_session(self, token: str | None) -> None:
        if token:
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

