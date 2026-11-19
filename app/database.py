
import sqlite3
import os

from pathlib import Path

# Database location
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

os.makedirs(INSTANCE_DIR, exist_ok=True)

def get_db_path():
    """Return the database path, allowing environment override for testing."""
    return Path(os.environ.get("LABSPACE_DB_PATH", str(INSTANCE_DIR / "computer_lab.db")))


def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all required database tables."""

    conn = get_db_connection()
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            student_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Workstations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workstations (
            pc_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'Available'
        )
    """)

    # Current allocations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            pc_id TEXT,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (pc_id) REFERENCES workstations(pc_id)
        )
    """)

    # Allocation history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS allocation_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            pc_id TEXT,
            action TEXT,
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Waiting queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waiting_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE,
            request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert five initial computers
    for i in range(1, 6):
        pc_id = f"PC-{i:02d}"

        cursor.execute("""
            INSERT OR IGNORE INTO workstations (pc_id, status)
            VALUES (?, 'Available')
        """, (pc_id,))

    conn.commit()
    conn.close()

    print("Database initialized successfully!")
