# database.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "users.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            faculty_id TEXT,
            faculty_name TEXT,
            course INTEGER,
            group_id TEXT,
            group_name TEXT,
            direction TEXT,
            setup_step TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "faculty_id": row[1],
            "faculty_name": row[2],
            "course": row[3],
            "group_id": row[4],
            "group_name": row[5],
            "direction": row[6],
            "setup_step": row[7],
        }
    return None


def save_user(user_id: int, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = get_user(user_id)
    if existing:
        sets = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        vals = list(kwargs.values()) + [user_id]
        c.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
    else:
        kwargs["user_id"] = user_id
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        c.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders})", list(kwargs.values()))
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()