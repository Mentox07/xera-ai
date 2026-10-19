import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
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

        CREATE TABLE IF NOT EXISTS projekte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            beschreibung TEXT DEFAULT '',
            anweisung TEXT DEFAULT '',
            erstellt_am TEXT DEFAULT (datetime('now')),
            geaendert_am TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projekt_notizen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id INTEGER NOT NULL,
            titel TEXT NOT NULL,
            inhalt TEXT DEFAULT '',
            geaendert_am TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (projekt_id) REFERENCES projekte(id)
        );

        CREATE TABLE IF NOT EXISTS projekt_dateien (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            pfad TEXT NOT NULL,
            groesse INTEGER DEFAULT 0,
            hochgeladen_am TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (projekt_id) REFERENCES projekte(id)
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
    if "projekt_id" not in cols:
        conn.execute("ALTER TABLE chat_sessions ADD COLUMN projekt_id INTEGER")

    msg_cols = [r["name"] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "extras" not in msg_cols:
        # Agent-Karten, Werkzeuge, Denkweg einer Antwort als JSON (karten.py)
        conn.execute("ALTER TABLE messages ADD COLUMN extras TEXT")

    user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "has_homelab" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN has_homelab INTEGER DEFAULT 0")
    if "roles_checked_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN roles_checked_at TEXT")
    if "prompt_heute" not in user_cols:
        # Gratis-Grenze je Tag (seit 2026-10-19): Fragen am Tag prompt_tag
        conn.execute("ALTER TABLE users ADD COLUMN prompt_heute INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE users ADD COLUMN prompt_tag TEXT")
    # Sandkasten-Kennung je Nutzer, fest und eindeutig (arbeitsbereich.uid_fuer, seit 2026-10-19)
    conn.execute("CREATE TABLE IF NOT EXISTS sandbox_uids (user_id TEXT PRIMARY KEY, uid INTEGER NOT NULL UNIQUE)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_zeit ON audit_log(created_at)")
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


def get_or_create_user(user_data: dict, rollen: dict | None) -> dict:
    """Beim Login: Konto anlegen oder auffrischen. ``rollen`` None heisst, Discord hat die
    Rollen gerade nicht verraten (auth.DiscordFehler) — dann bleiben die gespeicherten,
    statt dass ein Ausfall alle zu Gratis-Nutzern macht (2026-10-19)."""
    jetzt = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()

    if user:
        conn.execute(
            "UPDATE users SET username=?, avatar=?, email=?, last_login=? WHERE id=?",
            (user_data["username"], user_data.get("avatar"), user_data.get("email"), jetzt, user_data["id"])
        )
        if rollen is not None:
            conn.execute(
                "UPDATE users SET is_pro=?, is_admin=?, has_homelab=?, roles_checked_at=? WHERE id=?",
                (int(rollen["is_pro"]), int(rollen["is_admin"]), int(rollen["has_homelab"]), jetzt, user_data["id"])
            )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()
    else:
        rollen = rollen or {}
        conn.execute(
            "INSERT INTO users (id, username, discriminator, avatar, email, is_pro, is_admin, has_homelab, roles_checked_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_data["id"], user_data["username"], user_data.get("discriminator", "0"),
             user_data.get("avatar"), user_data.get("email"), int(bool(rollen.get("is_pro"))),
             int(bool(rollen.get("is_admin"))), int(bool(rollen.get("has_homelab"))), jetzt if rollen else None)
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_data["id"],)).fetchone()

    conn.close()
    return dict(user)


def heute_ch() -> str:
    """Heutiges Datum in der Schweiz — dort beginnt der Tag der Gratis-Fragen."""
    return datetime.now(ZoneInfo("Europe/Zurich")).date().isoformat()


def fragen_heute(user: dict) -> int:
    """Wie viele Fragen der Nutzer heute schon gestellt hat (Gratis-Grenze je Tag)."""
    return int(user.get("prompt_heute") or 0) if user.get("prompt_tag") == heute_ch() else 0


def increment_prompt_count(user_id: str) -> int:
    """Zählt eine Frage: insgesamt (prompt_count) und für heute (prompt_heute)."""
    heute = heute_ch()
    conn = get_db()
    conn.execute(
        "UPDATE users SET prompt_count = prompt_count + 1, "
        "prompt_heute = CASE WHEN prompt_tag = ? THEN prompt_heute + 1 ELSE 1 END, prompt_tag = ? WHERE id = ?",
        (heute, heute, user_id))
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


def save_message(session_id: int, role: str, content: str, extras: dict | None = None):
    conn = get_db()
    conn.execute("INSERT INTO messages (session_id, role, content, extras) VALUES (?, ?, ?, ?)",
                 (session_id, role, content, json.dumps(extras, ensure_ascii=False) if extras else None))
    conn.commit()
    conn.close()


def get_messages(session_id: int) -> list:
    conn = get_db()
    messages = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(m) for m in messages]


def get_messages_anzeige(session_id: int) -> list:
    """Wie get_messages, aber mit Agent-Karten/Werkzeugen/Denkweg an der
    Nachricht (Felder wie in web/src/daten/typen.ts). Nur für die Anzeige —
    get_messages bleibt schlicht, weil Teile davon ans Modell gehen."""
    conn = get_db()
    zeilen = conn.execute(
        "SELECT role, content, extras FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()
    conn.close()
    aus = []
    for z in zeilen:
        m = {"role": z["role"], "content": z["content"]}
        if z["extras"]:
            try:
                m.update(json.loads(z["extras"]))
            except (json.JSONDecodeError, TypeError):
                pass
        aus.append(m)
    return aus


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


# Gäste ohne Anmeldung (Prüfwert aus IP und Browserkennung, Tabelle guest_limits) gibt es
# seit 2026-10-19 nicht mehr: Eine neue Browserkennung gab neue Freifragen — anonymer
# Dauerzugang. Die Tabelle bleibt für die Zahlen in metrics.py.


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


def aktualisiere_rollen(user_id: str, *, is_pro: bool, is_admin: bool, has_homelab: bool) -> None:
    """Schreibt nachgeprüfte Rollen zurück, mit Zeitstempel.

    Der Zeitstempel ist der Zweck der Funktion: ohne ihn wüsste niemand, wie
    alt die gespeicherte Rolle ist, und es würde bei jeder Anfrage neu bei
    Discord nachgefragt.
    """
    conn = get_db()
    conn.execute(
        "UPDATE users SET is_pro=?, is_admin=?, has_homelab=?, roles_checked_at=? WHERE id=?",
        (int(is_pro), int(is_admin), int(has_homelab),
         datetime.now(timezone.utc).isoformat(), str(user_id)),
    )
    conn.commit()
    conn.close()


def sandbox_uid(user_id: str, wunsch: int, bereich: range) -> int:
    """Die Sandkasten-Kennung des Nutzers; beim ersten Mal vergeben: ``wunsch`` (die bisherige,
    aus dem Hash — so bleiben bestehende Ordner), wenn frei, sonst die kleinste freie in ``bereich``."""
    conn = get_db()
    try:
        r = conn.execute("SELECT uid FROM sandbox_uids WHERE user_id=?", (str(user_id),)).fetchone()
        if r:
            return int(r["uid"])
        vergeben = {int(x["uid"]) for x in conn.execute("SELECT uid FROM sandbox_uids")}
        uid = wunsch if wunsch not in vergeben else next(u for u in bereich if u not in vergeben)
        try:
            conn.execute("INSERT INTO sandbox_uids (user_id, uid) VALUES (?, ?)", (str(user_id), uid))
            conn.commit()
        except sqlite3.IntegrityError:   # gleichzeitig vergeben — die gespeicherte gilt
            return int(conn.execute("SELECT uid FROM sandbox_uids WHERE user_id=?", (str(user_id),)).fetchone()["uid"])
        return uid
    finally:
        conn.close()


def alle_user_ids() -> list[str]:
    """Alle Konten, die ältesten zuerst (main.startup reserviert ihre Sandkasten-Kennungen)."""
    conn = get_db()
    try:
        return [r["id"] for r in conn.execute("SELECT id FROM users ORDER BY rowid")]
    finally:
        conn.close()


def audit_aufraeumen(tage: int = 30) -> int:
    """Werkzeugprotokoll: Einträge älter als ``tage`` löschen (seit 2026-10-19, Datenschutz 6).
    Es hält auch Dateiinhalte fest — unbegrenzt aufbewahrt war das zu viel."""
    conn = get_db()
    try:
        n = conn.execute("DELETE FROM audit_log WHERE created_at < datetime('now', ?)", (f"-{int(tage)} days",)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def rollen_geprueft(user_id: str) -> None:
    """Nur den Zeitstempel setzen — Discord war gestört, die Rollen bleiben (rollen.py).
    So fragt Xera während einer Störung nicht bei jeder Anfrage erneut nach."""
    conn = get_db()
    conn.execute("UPDATE users SET roles_checked_at=? WHERE id=?",
                 (datetime.now(timezone.utc).isoformat(), str(user_id)))
    conn.commit()
    conn.close()


# --- Cowork: Arbeitsbereiche ------------------------------------------------
#
# Ein Projekt bündelt, was zu einem Vorhaben gehört: eine feste Anweisung,
# Notizen, Dateien und die Gespräche dazu. Der Zweck ist, den Zusammenhang
# nicht bei jedem Gespräch neu erklären zu müssen.
#
# Jede Funktion nimmt die Nutzerkennung entgegen und prüft sie mit. Ein
# Projekt anhand geschickter Nummer herauszugeben, ohne den Eigentümer zu
# prüfen, war im alten Backend genau die Lücke, die bei /api/chat offenstand.


def projekte_holen(user_id: str) -> list[dict]:
    conn = get_db()
    zeilen = conn.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM chat_sessions s WHERE s.projekt_id = p.id)
                      AS anzahl_gespraeche,
                  (SELECT COUNT(*) FROM projekt_dateien d WHERE d.projekt_id = p.id)
                      AS anzahl_dateien
             FROM projekte p
            WHERE p.user_id = ?
            ORDER BY p.geaendert_am DESC""",
        (str(user_id),),
    ).fetchall()
    conn.close()
    return [dict(z) for z in zeilen]


def projekt_holen(projekt_id: int, user_id: str) -> dict | None:
    """Gibt das Projekt nur heraus, wenn es dem Nutzer gehört."""
    conn = get_db()
    zeile = conn.execute(
        "SELECT * FROM projekte WHERE id = ? AND user_id = ?",
        (projekt_id, str(user_id)),
    ).fetchone()
    conn.close()
    return dict(zeile) if zeile else None


def projekt_anlegen(user_id: str, name: str, beschreibung: str = "", anweisung: str = "") -> dict:
    conn = get_db()
    zeiger = conn.execute(
        "INSERT INTO projekte (user_id, name, beschreibung, anweisung) VALUES (?,?,?,?)",
        (str(user_id), name, beschreibung, anweisung),
    )
    conn.commit()
    neu_id = zeiger.lastrowid
    conn.close()
    return projekt_holen(neu_id, user_id) or {}


def projekt_aendern(projekt_id: int, user_id: str, **felder) -> dict | None:
    erlaubt = {"name", "beschreibung", "anweisung"}
    zu_setzen = {k: v for k, v in felder.items() if k in erlaubt and v is not None}
    if not zu_setzen:
        return projekt_holen(projekt_id, user_id)

    conn = get_db()
    satz = ", ".join(f"{k}=?" for k in zu_setzen)
    conn.execute(
        f"UPDATE projekte SET {satz}, geaendert_am=datetime('now') WHERE id=? AND user_id=?",
        (*zu_setzen.values(), projekt_id, str(user_id)),
    )
    conn.commit()
    conn.close()
    return projekt_holen(projekt_id, user_id)


def projekt_loeschen(projekt_id: int, user_id: str) -> bool:
    """Löscht Projekt, Notizen und Dateiverweise.

    Die Gespräche bleiben stehen und verlieren nur ihre Zuordnung — jemand,
    der ein Projekt aufräumt, will selten seine Unterhaltungen verlieren.
    """
    if not projekt_holen(projekt_id, user_id):
        return False
    conn = get_db()
    conn.execute("DELETE FROM projekt_notizen WHERE projekt_id=?", (projekt_id,))
    conn.execute("DELETE FROM projekt_dateien WHERE projekt_id=?", (projekt_id,))
    conn.execute("UPDATE chat_sessions SET projekt_id=NULL WHERE projekt_id=?", (projekt_id,))
    conn.execute("DELETE FROM projekte WHERE id=? AND user_id=?", (projekt_id, str(user_id)))
    conn.commit()
    conn.close()
    return True


def notizen_holen(projekt_id: int) -> list[dict]:
    conn = get_db()
    zeilen = conn.execute(
        "SELECT * FROM projekt_notizen WHERE projekt_id=? ORDER BY geaendert_am DESC",
        (projekt_id,),
    ).fetchall()
    conn.close()
    return [dict(z) for z in zeilen]


def notiz_speichern(projekt_id: int, titel: str, inhalt: str, notiz_id: int | None = None) -> dict:
    conn = get_db()
    if notiz_id:
        conn.execute(
            "UPDATE projekt_notizen SET titel=?, inhalt=?, geaendert_am=datetime('now') "
            "WHERE id=? AND projekt_id=?",
            (titel, inhalt, notiz_id, projekt_id),
        )
    else:
        zeiger = conn.execute(
            "INSERT INTO projekt_notizen (projekt_id, titel, inhalt) VALUES (?,?,?)",
            (projekt_id, titel, inhalt),
        )
        notiz_id = zeiger.lastrowid
    conn.commit()
    zeile = conn.execute("SELECT * FROM projekt_notizen WHERE id=?", (notiz_id,)).fetchone()
    conn.close()
    return dict(zeile)


def notiz_loeschen(projekt_id: int, notiz_id: int) -> None:
    conn = get_db()
    conn.execute(
        "DELETE FROM projekt_notizen WHERE id=? AND projekt_id=?", (notiz_id, projekt_id)
    )
    conn.commit()
    conn.close()


def dateien_holen(projekt_id: int) -> list[dict]:
    conn = get_db()
    zeilen = conn.execute(
        "SELECT id, projekt_id, name, groesse, hochgeladen_am FROM projekt_dateien "
        "WHERE projekt_id=? ORDER BY hochgeladen_am DESC",
        (projekt_id,),
    ).fetchall()
    conn.close()
    return [dict(z) for z in zeilen]


def projektwissen(projekt_id: int) -> str:
    """Was dem Modell zu diesem Projekt vorangestellt wird.

    Bewusst knapp gehalten: Bei 16 384 Token Kontext kostet jede Zeile hier
    Platz, der für das eigentliche Gespräch fehlt. Notizen werden deshalb
    gekürzt, und es wird gesagt, dass gekürzt wurde — sonst wundert sich
    jemand, warum das Modell die letzte Notiz nicht kennt.
    """
    projekt = None
    conn = get_db()
    zeile = conn.execute("SELECT * FROM projekte WHERE id=?", (projekt_id,)).fetchone()
    if zeile:
        projekt = dict(zeile)
    conn.close()
    if not projekt:
        return ""

    teile = [f"Dieses Gespräch gehört zum Vorhaben „{projekt['name']}\"."]
    if projekt.get("beschreibung"):
        teile.append(projekt["beschreibung"])
    if projekt.get("anweisung"):
        teile.append(projekt["anweisung"])

    notizen = notizen_holen(projekt_id)
    if notizen:
        zeilen = []
        uebrig = 2500
        for n in notizen:
            stueck = f"- {n['titel']}: {n['inhalt']}".strip()
            if len(stueck) > uebrig:
                zeilen.append(f"({len(notizen) - len(zeilen)} weitere Notizen weggelassen)")
                break
            zeilen.append(stueck)
            uebrig -= len(stueck)
        teile.append("Notizen zum Vorhaben:\n" + "\n".join(zeilen))

    # Dateien zum Vorhaben (seit 2026-10-01). Der herausgezogene Text liegt
    # als .txt neben der Datenbank; hier geht ein Auszug mit, je Datei
    # gekuerzt und insgesamt begrenzt — der Kontext hat 64k Token, aber jede
    # Zeile hier kostet bei jeder Frage Einlesezeit.
    from pathlib import Path as _Pfad
    conn = get_db()
    dateien = conn.execute(
        "SELECT name, pfad FROM projekt_dateien WHERE projekt_id=? ORDER BY hochgeladen_am DESC",
        (projekt_id,),
    ).fetchall()
    conn.close()
    if dateien:
        stuecke, rest = [], 24000
        for d in dateien:
            try:
                text = _Pfad(d["pfad"]).read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if rest <= 0:
                stuecke.append(f"[{d['name']}: weggelassen, Platz aufgebraucht]")
                continue
            auszug = text[: min(8000, rest)]
            rest -= len(auszug)
            gekuerzt = " (gekuerzt)" if len(auszug) < len(text) else ""
            stuecke.append(f"### {d['name']}{gekuerzt}\n{auszug}")
        if stuecke:
            teile.append("Dateien zum Vorhaben:\n\n" + "\n\n".join(stuecke))

    return "\n\n".join(teile)


def datei_anlegen(projekt_id: int, name: str, pfad: str, groesse: int) -> dict:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projekt_dateien (projekt_id, name, pfad, groesse) VALUES (?, ?, ?, ?)",
        (projekt_id, name, pfad, groesse),
    )
    conn.commit()
    zeile = conn.execute(
        "SELECT id, projekt_id, name, groesse, hochgeladen_am FROM projekt_dateien WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return dict(zeile)


def datei_holen(projekt_id: int, datei_id: int) -> dict | None:
    conn = get_db()
    zeile = conn.execute(
        "SELECT * FROM projekt_dateien WHERE id=? AND projekt_id=?", (datei_id, projekt_id)
    ).fetchone()
    conn.close()
    return dict(zeile) if zeile else None


def datei_loeschen(projekt_id: int, datei_id: int) -> None:
    conn = get_db()
    conn.execute("DELETE FROM projekt_dateien WHERE id=? AND projekt_id=?", (datei_id, projekt_id))
    conn.commit()
    conn.close()


def projekt_gespraeche(projekt_id: int, user_id: str) -> list[dict]:
    conn = get_db()
    zeilen = conn.execute(
        "SELECT * FROM chat_sessions WHERE projekt_id=? AND user_id=? ORDER BY created_at DESC",
        (projekt_id, user_id),
    ).fetchall()
    conn.close()
    return [dict(z) for z in zeilen]


def sitzung_an_projekt(session_id: int, projekt_id: int) -> None:
    """Ordnet ein Gespräch einem Vorhaben zu."""
    conn = get_db()
    conn.execute("UPDATE chat_sessions SET projekt_id=? WHERE id=?", (projekt_id, session_id))
    conn.commit()
    conn.close()
