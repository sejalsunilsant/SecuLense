"""Local-only auth and data API for the React dashboard.

This server is intentionally restricted to loopback. It is suitable for a
single-user local demo, not for deployment on a public network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

try:
    from dotenv import dotenv_values
except ImportError:  # Keep the local demo usable without the optional dotenv package.
    dotenv_values = None


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "frontend" / "private" / "dashboard.json"
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
            row = db.execute("SELECT id,username,password_salt,password_hash FROM users WHERE username=?", (username,)).fetchone()
        if row is None:
            # Keep the work factor similar when the username does not exist.
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
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (
                hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat(),
            ))
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


class LocalDashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, store: AuthStore, data_file: Path):
        super().__init__(address, handler)
        self.auth_store = store
        self.data_file = data_file
        self.login_attempts: dict[str, list[float]] = {}
        self.signup_attempts: dict[str, list[float]] = {}
        self.market_cache: dict[str, tuple[float, dict]] = {}
        env_file = ROOT / ".env"
        file_values = dotenv_values(env_file) if dotenv_values and env_file.exists() else {}
        self.massive_api_key = os.environ.get("MASSIVE_API_KEY") or (file_values or {}).get("MASSIVE_API_KEY") or ""


class Handler(BaseHTTPRequestHandler):
    server: LocalDashboardServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"[dashboard-api] {self.address_string()} {fmt % args}")

    def send_json(self, status: int, payload: dict, cookie: str | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request body.") from exc
        if length <= 0 or length > 8192:
            raise ValueError("Request body is empty or too large.")
        raw = self.rfile.read(length)
        try:
            result = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request must contain valid JSON.") from exc
        if not isinstance(result, dict):
            raise ValueError("Request must contain a JSON object.")
        return result

    def cookie_token(self) -> str | None:
        parsed = SimpleCookie()
        try:
            parsed.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = parsed.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def current_user(self) -> dict | None:
        return self.server.auth_store.get_session_user(self.cookie_token())

    def massive_daily_bars(self, ticker: str) -> dict:
        """Fetch split-adjusted daily US stock bars without exposing credentials to React."""
        cached = self.server.market_cache.get(ticker)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
        if not self.server.massive_api_key:
            return {"provider_configured": False, "results": []}
        today = datetime.now(ZoneInfo("America/New_York")).date()
        start = today - timedelta(days=370)
        query = urlencode({"adjusted": "true", "sort": "asc", "limit": "5000"})
        url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{today.isoformat()}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "SecuLense local research dashboard", "Authorization": f"Bearer {self.server.massive_api_key}"})
        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            # Keep error details useful while never returning the key-bearing URL.
            return {"provider_configured": True, "error": f"Could not fetch Massive daily prices ({type(exc).__name__}).", "results": []}
        if payload.get("status") not in {"OK", "DELAYED"}:
            return {"provider_configured": True, "error": str(payload.get("message") or payload.get("status") or "Provider returned no price data."), "results": []}
        results = []
        for row in payload.get("results", []):
            try:
                stamp = datetime.fromtimestamp(float(row["t"]) / 1000, tz=timezone.utc).astimezone(ZoneInfo("America/New_York"))
                results.append({"ticker": ticker, "trade_date": stamp.date().isoformat(), "open": row.get("o"), "high": row.get("h"), "low": row.get("l"), "close": row.get("c"), "adjusted_close": row.get("c"), "volume": row.get("v"), "data_source": "Massive real market data", "is_synthetic": False})
            except (KeyError, TypeError, ValueError, OSError):
                continue
        result = {"provider_configured": True, "source": "Massive", "data_mode": "live_provider", "updated_at": datetime.now(timezone.utc).isoformat(), "results": results}
        self.server.market_cache[ticker] = (time.monotonic(), result)
        return result

    def origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            return False
        return host in {"127.0.0.1", "localhost"} and port in {5173, 4173}

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/auth/status":
            return self.send_json(HTTPStatus.OK, {"setup_required": self.server.auth_store.user_count() == 0})
        if route == "/api/auth/me":
            user = self.current_user()
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Sign in to continue."})
            return self.send_json(HTTPStatus.OK, {"user": user})
        if route == "/api/data":
            if not self.current_user():
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Sign in to continue."})
            try:
                payload = json.loads(self.server.data_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Dashboard data is unavailable. Restart the local dashboard."})
            return self.send_json(HTTPStatus.OK, payload)
        if route == "/api/market-data":
            if not self.current_user():
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Sign in to continue."})
            from urllib.parse import parse_qs
            ticker = parse_qs(urlparse(self.path).query).get("ticker", [""])[0].upper()
            if not re.fullmatch(r"[A-Z0-9.]{1,12}", ticker):
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter a valid US stock ticker."})
            payload = self.massive_daily_bars(ticker)
            status = HTTPStatus.BAD_GATEWAY if payload.get("error") else HTTPStatus.OK
            return self.send_json(status, payload)
        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self):
        if not self.origin_allowed():
            return self.send_json(HTTPStatus.FORBIDDEN, {"error": "Request origin is not allowed."})
        route = urlparse(self.path).path
        try:
            body = self.read_body()
        except ValueError as exc:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if route == "/api/auth/setup":
            try:
                user = self.server.auth_store.create_first_user(str(body.get("username", "")), str(body.get("password", "")))
            except ValueError as exc:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except RuntimeError as exc:
                return self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
            token, _expires = self.server.auth_store.create_session(user["id"])
            cookie = f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}"
            return self.send_json(HTTPStatus.CREATED, {"user": user}, cookie)

        if route == "/api/auth/signup":
            address = self.client_address[0]
            now = time.monotonic()
            attempts = [stamp for stamp in self.server.signup_attempts.get(address, []) if now - stamp < 300]
            if len(attempts) >= 5:
                return self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Too many account-creation attempts. Wait a few minutes and try again."})
            attempts.append(now)
            self.server.signup_attempts[address] = attempts
            try:
                user = self.server.auth_store.create_user(str(body.get("username", "")), str(body.get("password", "")))
            except ValueError as exc:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            token, _expires = self.server.auth_store.create_session(user["id"])
            cookie = f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}"
            return self.send_json(HTTPStatus.CREATED, {"user": user}, cookie)

        if route == "/api/auth/login":
            address = self.client_address[0]
            now = time.monotonic()
            attempts = [stamp for stamp in self.server.login_attempts.get(address, []) if now - stamp < 300]
            if len(attempts) >= 8:
                return self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Too many sign-in attempts. Wait a few minutes and try again."})
            attempts.append(now)
            self.server.login_attempts[address] = attempts
            user = self.server.auth_store.authenticate(str(body.get("username", "")), str(body.get("password", "")))
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Username or password is incorrect."})
            self.server.login_attempts.pop(address, None)
            token, _expires = self.server.auth_store.create_session(user["id"])
            cookie = f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}"
            return self.send_json(HTTPStatus.OK, {"user": user}, cookie)

        if route == "/api/auth/logout":
            self.server.auth_store.revoke_session(self.cookie_token())
            cookie = f"{COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
            return self.send_json(HTTPStatus.OK, {"ok": True}, cookie)

        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})


def main():
    host = "127.0.0.1"
    port = int(os.environ.get("SECULENSE_API_PORT", "8765"))
    server = LocalDashboardServer((host, port), Handler, AuthStore(), DATA_FILE)
    print(f"SecuLense local auth/data API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
