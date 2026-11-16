import sqlite3
from pathlib import Path

DB_PATH = Path("data/guild_settings.db")

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_guild_settings_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (guild_id, section, key)
            )
        ''')

def get_settings(guild_id: int) -> list[tuple[str, str, str]]:
    with get_connection() as conn:
        cur = conn.execute('''
            SELECT section, key, value
            FROM guild_settings
            WHERE guild_id = ?
        ''', (guild_id,))
        return cur.fetchall()

def set_setting(guild_id: int, section: str, key: str, value):
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO guild_settings (guild_id, section, key, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, section, key) DO UPDATE SET value=excluded.value
        ''', (guild_id, section, key, None if value is None else str(value)))    

def has_setting(guild_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute('''
            SELECT 1
            FROM guild_settings
            WHERE guild_id = ?
            LIMIT 1
        ''', (guild_id,))
        return cur.fetchone() is not None