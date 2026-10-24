import sqlite3
from pathlib import Path
from datetime import datetime


DB_PATH = Path("data/member_log.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_member_log_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS member_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                event TEXT NOT NULL,
                account_created_at TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_member_log_user ON member_log (guild_id, user_id)"
        )


def log_member_event(guild_id: int, user_id: int, username: str, event: str, account_created_at:datetime):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO member_log (guild_id, user_id, username, event, account_created_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, username, event, account_created_at.strftime("%Y-%m-%d %H:%M:%S"))
        )


def get_member_history(guild_id: int, user_id: int, limit: int = 20) -> list:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT event, username, created_at FROM member_log 
            WHERE guild_id = ? AND user_id = ? 
            ORDER BY id DESC LIMIT ?
            """,
            (guild_id, user_id, limit)
        )
        return cur.fetchall()

def cleanup_member_log(months:int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            DELETE FROM member_log
            WHERE datetime(created_at) < datetime('now', ?)
            """,
            (f'-{months} months',)
        )    
        return cur.rowcount  # Return the number of deleted rows