import os
import aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./titan.db")
db_path = DATABASE_URL.replace("sqlite:///", "")

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        encrypted_key TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        asset TEXT NOT NULL,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER NOT NULL,
        direction TEXT,
        confidence REAL,
        payload TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(analysis_id) REFERENCES analyses(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER NOT NULL,
        entry_price REAL,
        stop_loss REAL,
        target1 REAL,
        target2 REAL,
        status TEXT,
        pnl REAL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_debates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER NOT NULL,
        bull_json TEXT,
        bear_json TEXT,
        judge_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(analysis_id) REFERENCES analyses(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bayesian_weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        weight REAL NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_quality_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER NOT NULL,
        passed INTEGER NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(analysis_id) REFERENCES analyses(id)
    )
    """,
]


def get_db_path() -> str:
    return db_path


async def init_db() -> None:
    async with aiosqlite.connect(db_path) as connection:
        for statement in CREATE_TABLES_SQL:
            await connection.execute(statement)
        await connection.commit()
