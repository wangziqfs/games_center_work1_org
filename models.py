import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'blackjack.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS matches (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code       TEXT NOT NULL,
            player1_id      INTEGER NOT NULL,
            player2_id      INTEGER,
            winner          TEXT,
            p1_final_value  INTEGER,
            p2_final_value  INTEGER,
            played_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES users(id),
            FOREIGN KEY (player2_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH)


if __name__ == '__main__':
    init_db()
