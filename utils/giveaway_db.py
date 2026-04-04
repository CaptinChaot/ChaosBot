import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/giveaway.db")

def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_giveaway_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER,
            prize TEXT NOT NULL,
            winner_count INTEGER NOT NULL,
            ends_at TEXT,
            ended INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS giveaway_entries (
            giveaway_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (giveaway_id, user_id),
            FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
        )
        """)

def create_giveaway(guild_id: int, channel_id: int, prize: str, winner_count: int, ends_at: datetime | None, created_by: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO giveaways (guild_id, channel_id, prize, winner_count, ends_at, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, prize, winner_count, ends_at.isoformat() if ends_at else None, created_by, datetime.utcnow().isoformat())
        )
        return cur.lastrowid

def set_message_id(giveaway_id: int, message_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id))

def add_entry(giveaway_id: int, user_id: int) -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
                (giveaway_id, user_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False  # Bereits eingetragen

def remove_entry(giveaway_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id)
        )

def is_entered(giveaway_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT 1 FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id)
        )
        return cur.fetchone() is not None

def get_entry_count(giveaway_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,)
        )
        return cur.fetchone()[0]

def get_entries(giveaway_id: int) -> list[int]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,)
        )
        return [row[0] for row in cur.fetchall()]

def get_giveaway(giveaway_id: int) -> dict | None:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,))
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "guild_id": row[1], "channel_id": row[2],
        "message_id": row[3], "prize": row[4], "winner_count": row[5],
        "ends_at": datetime.fromisoformat(row[6]) if row[6] else None,
        "ended": bool(row[7]), "created_by": row[8], "created_at": row[9]
    }

def get_active_giveaways(guild_id: int) -> list[dict]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM giveaways WHERE guild_id = ? AND ended = 0",
            (guild_id,)
        )
        rows = cur.fetchall()
    return [get_giveaway(row[0]) for row in rows]

def end_giveaway(giveaway_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,))