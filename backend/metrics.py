from . import database as db


def _q(sql: str, params=()):
    conn = db.get_db()
    val = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return val or 0


def _rows(sql: str, params=()):
    conn = db.get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def generate_metrics() -> str:
    lines = []

    def gauge(name: str, help_text: str, value, labels: dict | None = None):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        label_str = ""
        if labels:
            parts = ",".join(f'{k}="{v}"' for k, v in labels.items())
            label_str = "{" + parts + "}"
        lines.append(f"{name}{label_str} {value}")

    # Users
    users_all = _q("SELECT COUNT(*) FROM users")
    users_pro = _q("SELECT COUNT(*) FROM users WHERE is_pro=1")
    lines.append("# HELP xera_users_total Total registered users")
    lines.append("# TYPE xera_users_total gauge")
    lines.append(f'xera_users_total{{type="all"}} {users_all}')
    lines.append(f'xera_users_total{{type="pro"}} {users_pro}')

    gauge("xera_guests_total", "Total unique guest fingerprints",
          _q("SELECT COUNT(*) FROM guest_limits"))

    # Prompts
    gauge("xera_prompts_total", "Total prompts by registered users",
          _q("SELECT COALESCE(SUM(prompt_count),0) FROM users"))
    gauge("xera_guest_prompts_total", "Total prompts by guests",
          _q("SELECT COALESCE(SUM(prompt_count),0) FROM guest_limits"))

    # Messages
    gauge("xera_messages_total", "Total messages",
          _q("SELECT COUNT(*) FROM messages"))
    gauge("xera_messages_last_24h", "Messages in the last 24 hours",
          _q("SELECT COUNT(*) FROM messages WHERE created_at >= datetime('now','-24 hours')"))

    msg_by_role = _rows("SELECT role, COUNT(*) AS cnt FROM messages GROUP BY role")
    lines.append("# HELP xera_messages_by_role Messages grouped by role")
    lines.append("# TYPE xera_messages_by_role gauge")
    for row in msg_by_role:
        lines.append(f'xera_messages_by_role{{role="{row["role"]}"}} {row["cnt"]}')

    # Sessions
    gauge("xera_sessions_total", "Total chat sessions",
          _q("SELECT COUNT(*) FROM chat_sessions"))

    sessions_by_mode = _rows("SELECT mode, COUNT(*) AS cnt FROM chat_sessions GROUP BY mode")
    lines.append("# HELP xera_sessions_by_mode Sessions grouped by mode")
    lines.append("# TYPE xera_sessions_by_mode gauge")
    for row in sessions_by_mode:
        mode = row.get("mode") or "chat"
        lines.append(f'xera_sessions_by_mode{{mode="{mode}"}} {row["cnt"]}')

    # Audit log
    gauge("xera_audit_total", "Total audit log entries",
          _q("SELECT COUNT(*) FROM audit_log"))
    gauge("xera_audit_approved", "Approved tool executions",
          _q("SELECT COUNT(*) FROM audit_log WHERE approved=1"))
    gauge("xera_audit_denied", "Denied tool executions",
          _q("SELECT COUNT(*) FROM audit_log WHERE approved=0"))

    audit_by_tool = _rows(
        "SELECT tool, level, COUNT(*) AS cnt FROM audit_log GROUP BY tool, level"
    )
    lines.append("# HELP xera_audit_by_tool Audit entries by tool and level")
    lines.append("# TYPE xera_audit_by_tool gauge")
    for row in audit_by_tool:
        lines.append(f'xera_audit_by_tool{{tool="{row["tool"]}",level="{row["level"]}"}} {row["cnt"]}')

    # Self-learning
    gauge("xera_learnings_total", "Total self-learning entries",
          _q("SELECT COUNT(*) FROM learning_logs"))

    # Active users (by last message timestamp)
    gauge("xera_active_users_1h", "Users with a message in the last 1 hour",
          _q("""SELECT COUNT(DISTINCT cs.user_id) FROM messages m
                JOIN chat_sessions cs ON cs.id = m.session_id
                WHERE m.role='user' AND m.created_at >= datetime('now','-1 hour')"""))
    gauge("xera_active_users_24h", "Users with a message in the last 24 hours",
          _q("""SELECT COUNT(DISTINCT cs.user_id) FROM messages m
                JOIN chat_sessions cs ON cs.id = m.session_id
                WHERE m.role='user' AND m.created_at >= datetime('now','-24 hours')"""))

    # Per-user metrics (for User Activity dashboard)
    per_user_prompts = _rows(
        "SELECT u.username, u.prompt_count FROM users u ORDER BY u.prompt_count DESC"
    )
    lines.append("# HELP xera_user_prompts_total Total prompts per user")
    lines.append("# TYPE xera_user_prompts_total gauge")
    for row in per_user_prompts:
        u = row["username"].replace('"', '\\"')
        lines.append(f'xera_user_prompts_total{{user="{u}"}} {row["prompt_count"]}')

    per_user_sessions = _rows(
        "SELECT u.username, COUNT(cs.id) AS cnt FROM users u "
        "LEFT JOIN chat_sessions cs ON cs.user_id = u.id "
        "GROUP BY u.id ORDER BY cnt DESC"
    )
    lines.append("# HELP xera_user_sessions_total Total sessions per user")
    lines.append("# TYPE xera_user_sessions_total gauge")
    for row in per_user_sessions:
        u = row["username"].replace('"', '\\"')
        lines.append(f'xera_user_sessions_total{{user="{u}"}} {row["cnt"]}')

    per_user_messages = _rows(
        "SELECT u.username, COUNT(m.id) AS cnt FROM users u "
        "JOIN chat_sessions cs ON cs.user_id = u.id "
        "JOIN messages m ON m.session_id = cs.id AND m.role = 'user' "
        "GROUP BY u.id ORDER BY cnt DESC"
    )
    lines.append("# HELP xera_user_messages_total Total user-role messages per user")
    lines.append("# TYPE xera_user_messages_total gauge")
    for row in per_user_messages:
        u = row["username"].replace('"', '\\"')
        lines.append(f'xera_user_messages_total{{user="{u}"}} {row["cnt"]}')

    return "\n".join(lines) + "\n"
