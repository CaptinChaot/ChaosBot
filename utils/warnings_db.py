import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/warnings.db")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


# ==================================================
# INIT / MIGRATION
# ==================================================

def init_db():
    with get_connection() as conn:

        # ---- WARNINGS ----
        conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            auto_action_type TEXT,
            auto_action_at TEXT
        )
        """)

        # ---- MIGRATION CHECK ----
        cur = conn.execute("PRAGMA table_info(warnings)")
        cols = {row[1] for row in cur.fetchall()}

        if "auto_action_type" not in cols:
            conn.execute("ALTER TABLE warnings ADD COLUMN auto_action_type TEXT")

        if "auto_action_at" not in cols:
            conn.execute("ALTER TABLE warnings ADD COLUMN auto_action_at TEXT")

        # ---- PUNISHMENTS ----
        conn.execute("""
        CREATE TABLE IF NOT EXISTS punishments (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            active_timeout_until TEXT,
            active_ban INTEGER DEFAULT 0,
            reason TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
        """)


# ==================================================
# WARNINGS
# ==================================================

def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, moderator_id, reason, datetime.utcnow().isoformat())
        )
        return cur.lastrowid


def count_warnings(guild_id: int, user_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return cur.fetchone()[0]
    
def delete_warnings(guild_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM warnings
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )

def get_last_warning_id(guild_id: int, user_id: int) -> int | None:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id, user_id)
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_warning_by_id(warn_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT auto_action_type FROM warnings WHERE id = ?",
            (warn_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def delete_warning_by_id(warn_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM warnings WHERE id = ?", (warn_id,))


# ==================================================
# AUTO-ACTIONS
# ==================================================

def get_last_auto_action(guild_id: int, user_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT auto_action_type, auto_action_at
            FROM warnings
            WHERE guild_id = ?
              AND user_id = ?
              AND auto_action_at IS NOT NULL
            ORDER BY auto_action_at DESC
            LIMIT 1
            """,
            (guild_id, user_id)
        )
        row = cur.fetchone()

    if not row:
        return None

    action_type, action_at = row
    return {
        "type": action_type,
        "at": datetime.fromisoformat(action_at)
    }


def mark_auto_action(warning_id: int, action_type: str):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE warnings
            SET auto_action_type = ?, auto_action_at = ?
            WHERE id = ?
            """,
            (action_type, datetime.utcnow().isoformat(), warning_id)
        )


def auto_action_allowed(last_action, cooldown_seconds: int) -> bool:
    if not last_action:
        return True
    return (datetime.utcnow() - last_action["at"]).total_seconds() >= cooldown_seconds


# ==================================================
# PUNISHMENTS (STATUS)
# ==================================================

def get_punishment(guild_id: int, user_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT active_timeout_until, active_ban
            FROM punishments
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )
        row = cur.fetchone()

    if not row:
        return None

    timeout_until, active_ban = row
    return {
        "active_timeout_until": (
            datetime.fromisoformat(timeout_until)
            if timeout_until else None
        ),
        "active_ban": bool(active_ban),
    }

def save_timeout(guild_id: int, user_id: int, until: datetime, reason: str | None = None):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO punishments (guild_id, user_id, active_timeout_until, reason)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET active_timeout_until = excluded.active_timeout_until, reason = excluded.reason
            """,
            (guild_id, user_id, until.isoformat(), reason)
            )
            
def clear_timeout(guild_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE punishments
            SET active_timeout_until = NULL,
                reason = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )

def save_ban(guild_id: int, user_id: int, reason: str | None = None):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO punishments (guild_id, user_id, active_ban, reason)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET active_ban = 1, reason = excluded.reason
            """,
            (guild_id, user_id, reason)
        )


def clear_ban(guild_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE punishments
            SET active_ban = 0, reason = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )

def get_user_status(guild_id: int, user_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM warnings
                 WHERE guild_id = ? AND user_id = ?) AS warn_count,
                active_timeout_until,
                active_ban,
                reason
            FROM punishments
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id, guild_id, user_id)
        )
        row = cur.fetchone()

    if not row:
        return {
            "warns": 0,
            "timeout_until": None,
            "active_ban": False,
            "reason": None,
        }

    warns, timeout_until, active_ban, reason = row
    return {
        "warns": warns,
        "timeout_until": (
            datetime.fromisoformat(timeout_until)
            if timeout_until else None
        ),
        "active_ban": bool(active_ban),
        "reason": reason,
    }
