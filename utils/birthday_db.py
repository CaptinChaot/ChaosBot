import sqlite3
from pathlib import Path

DB_PATH = Path("data/birthday.db")

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_birthday_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS birthdays (
                guild_id INTIGER NOT NULL,
                user_id INTEGER NOT NULL,
                day INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')

def save_birthday(guild_id: int, user_id: int, day: int, month: int, year: int):
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO birthdays (guild_id, user_id, day, month, year)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) 
            DO UPDATE SET day=excluded.day, month=excluded.month, year=excluded.year
            ''', 
            (guild_id, user_id, day, month, year)
            )

def get_birthday(guild_id: int, user_id: int) -> dict | None:       
    with get_connection() as conn:
        cur = conn.execute(
            'SELECT day, month, year FROM birthdays WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)
            ) 
        row = cur.fetchone()
    if not row:
        return None
    return {'day': row[0], 'month': row[1], 'year': row[2]}

def get_todays_birthdays(guild_id: int, day: int, month: int) -> list[int]:
    with get_connection() as conn:
        cur = conn.execute(
            'SELECT user_id FROM birthdays WHERE guild_id = ? AND day = ? AND month = ?', 
            (guild_id, day, month),
        )
        return [row[0] for row in cur.fetchall()]