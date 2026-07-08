import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from . import config


def get_db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            discriminator TEXT DEFAULT '0',
            avatar TEXT,
            email TEXT,
            is_admin INTEGER DEFAULT 0,
            is_pro INTEGER DEFAULT 0,
            prompt_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT 'Neuer Chat',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id INTEGER,
            tool TEXT NOT NULL,
            args TEXT,
            level TEXT NOT NULL,
            approved INTEGER DEFAULT 1,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS guest_limits (
            fingerprint TEXT PRIMARY KEY,
            prompt_count INTEGER DEFAULT 0,
            first_seen TEXT DEFAULT (datetime('now')),
            last_used TEXT DEFAULT (datetime('now'))
        );
    """)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_sessions)").fetchall()]
    if "mode" not in cols:
        conn.execute("ALTER TABLE chat_sessions ADD COLUMN mode TEXT DEFAULT 'chat'")
    if "folder" not in cols:
        conn.execute("ALTER TABLE chat_sessions ADD COLUMN folder TEXT DEFAULT NULL")
    user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "has_homelab" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN has_homelab INTEGER DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id INTEGER,
            topic TEXT NOT NULL,
            learning TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cli_tokens (
            state TEXT PRIMARY KEY,
            token TEXT,
            user_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ssh_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            public_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,
            name TEXT DEFAULT 'default',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def ssh_key_add(user_id: str, public_key: str, fingerprint: str, name: str = "default") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT OR REPLACE INTO ssh_keys (user_id, public_key, fingerprint, name) VALUES (?, ?, ?, ?)",
        (user_id, public_key, fingerprint, name),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def ssh_key_list(user_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, fingerprint, name, created_at FROM ssh_keys WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ssh_key_delete(user_id: str, key_id: int) -> bool:
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM ssh_keys WHERE id = ? AND user_id = ?", (key_id, user_id)
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def ssh_key_all() -> list[dict]:
    """Return all keys with user info — used by the authorized_keys sync service."""
    conn = get_db()
    rows = conn.execute(
        "SELECT s.id, s.user_id, s.public_key, s.fingerprint, s.name, u.username "
        "FROM ssh_keys s JOIN users u ON s.user_id = u.id ORDER BY s.id",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_or_create_user(user_data: dict, is_pro: bool = False, is_admin: bool = False, has_homelab: bool = False) -> dict:
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()

    if user:
        conn.execute(
            "UPDATE users SET username=?, avatar=?, email=?, is_pro=?, is_admin=?, has_homelab=?, last_login=? WHERE id=?",
            (user_data["username"], user_data.get("avatar"), user_data.get("email"),
             int(is_pro), int(is_admin), int(has_homelab), datetime.now(timezone.utc).isoformat(), user_data["id"])
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()
    else:
        conn.execute(
            "INSERT INTO users (id, username, discriminator, avatar, email, is_pro, is_admin, has_homelab) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_data["id"], user_data["username"], user_data.get("discriminator", "0"),
             user_data.get("avatar"), user_data.get("email"), int(is_pro), int(is_admin), int(has_homelab))
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()

    conn.close()
    return dict(user)


def increment_prompt_count(user_id: str) -> int:
    conn = get_db()
    conn.execute("UPDATE users SET prompt_count = prompt_count + 1 WHERE id = ?", (user_id,))
    conn.commit()
    row = conn.execute("SELECT prompt_count FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["prompt_count"]


def get_user(user_id: str) -> dict | None:
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def create_session(user_id: str, title: str = "Neuer Chat", mode: str = "chat") -> int:
    conn = get_db()
    cursor = conn.execute("INSERT INTO chat_sessions (user_id, title, mode) VALUES (?, ?, ?)", (user_id, title, mode))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_session(session_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sessions(user_id: str, mode: str | None = None) -> list:
    conn = get_db()
    if mode:
        sessions = conn.execute(
            "SELECT * FROM chat_sessions WHERE user_id = ? AND mode = ? ORDER BY created_at DESC",
            (user_id, mode),
        ).fetchall()
    else:
        sessions = conn.execute(
            "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    conn.close()
    return [dict(s) for s in sessions]


def save_message(session_id: int, role: str, content: str):
    conn = get_db()
    conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                 (session_id, role, content))
    conn.commit()
    conn.close()


def get_messages(session_id: int) -> list:
    conn = get_db()
    messages = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(m) for m in messages]


def update_session_title(session_id: int, title: str):
    conn = get_db()
    conn.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()


def update_session_folder(session_id: int, folder: str | None):
    conn = get_db()
    conn.execute("UPDATE chat_sessions SET folder = ? WHERE id = ?", (folder, session_id))
    conn.commit()
    conn.close()


def get_folders(user_id: str, mode: str | None = None) -> list[str]:
    conn = get_db()
    if mode:
        rows = conn.execute(
            "SELECT DISTINCT folder FROM chat_sessions WHERE user_id = ? AND mode = ? AND folder IS NOT NULL ORDER BY folder",
            (user_id, mode),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT folder FROM chat_sessions WHERE user_id = ? AND folder IS NOT NULL ORDER BY folder",
            (user_id,),
        ).fetchall()
    conn.close()
    return [r["folder"] for r in rows]


def delete_session(session_id: int):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def log_audit(user_id: str, session_id: int | None, tool: str, args: str, level: str, approved: bool, result: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (user_id, session_id, tool, args, level, approved, result) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, session_id, tool, args, level, int(approved), result),
    )
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 50) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_learning(user_id: str, session_id: int | None, topic: str, learning: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO learning_logs (user_id, session_id, topic, learning) VALUES (?, ?, ?, ?)",
        (user_id, session_id, topic, learning),
    )
    conn.commit()
    conn.close()


def get_recent_learnings(user_id: str, limit: int = 10) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT topic, learning, created_at FROM learning_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def make_fingerprint(ip: str, user_agent: str) -> str:
    raw = f"{ip}|{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_guest_prompt_count(fingerprint: str) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT prompt_count FROM guest_limits WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    conn.close()
    return row["prompt_count"] if row else 0


def increment_guest_prompt_count(fingerprint: str) -> int:
    conn = get_db()
    conn.execute(
        """INSERT INTO guest_limits (fingerprint, prompt_count, last_used)
           VALUES (?, 1, datetime('now'))
           ON CONFLICT(fingerprint)
           DO UPDATE SET prompt_count = prompt_count + 1, last_used = datetime('now')""",
        (fingerprint,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT prompt_count FROM guest_limits WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    conn.close()
    return row["prompt_count"]


# --- CLI Token Auth ---

def cli_auth_create_state(state: str):
    """Create a pending CLI auth state (expires in 10 minutes)."""
    conn = get_db()
    conn.execute(
        """INSERT INTO cli_tokens (state, status, expires_at)
           VALUES (?, 'pending', datetime('now', '+10 minutes'))""",
        (state,),
    )
    conn.commit()
    conn.close()


def cli_auth_complete(state: str, user_id: str, token: str):
    """Mark CLI auth state as complete with token."""
    conn = get_db()
    conn.execute(
        """UPDATE cli_tokens SET status = 'complete', token = ?, user_id = ?
           WHERE state = ? AND status = 'pending'""",
        (token, user_id, state),
    )
    conn.commit()
    conn.close()


def cli_auth_poll(state: str) -> dict | None:
    """Poll CLI auth state. Returns None if not found/expired."""
    conn = get_db()
    row = conn.execute(
        """SELECT status, token, user_id FROM cli_tokens
           WHERE state = ? AND expires_at > datetime('now')""",
        (state,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_cli_token(token: str) -> dict | None:
    """Resolve a CLI bearer token to a user."""
    conn = get_db()
    row = conn.execute(
        "SELECT user_id FROM cli_tokens WHERE token = ? AND status = 'complete'",
        (token,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    user = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
    conn.close()
    return dict(user) if user else None
