"""
database.py - Database Connection and Schema Management for Library Management System
Handles SQLite initialization, table creation, indexes, and connection utilities.
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, date

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_system.db")

@contextmanager
def get_db_connection():
    """Provides a transactional database connection with row-factory and WAL mode enabled."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(reset=False):
    """Initializes tables, indexes, and system default configuration."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if reset:
            cursor.executescript("""
                DROP TABLE IF EXISTS audit_logs;
                DROP TABLE IF EXISTS simulation_events;
                DROP TABLE IF EXISTS fine_payments;
                DROP TABLE IF EXISTS reservations;
                DROP TABLE IF EXISTS loans;
                DROP TABLE IF EXISTS patrons;
                DROP TABLE IF EXISTS books;
                DROP TABLE IF EXISTS system_config;
            """)

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                publication_year INTEGER NOT NULL,
                shelf_location TEXT NOT NULL,
                total_copies INTEGER NOT NULL DEFAULT 1 CHECK (total_copies >= 0),
                available_copies INTEGER NOT NULL DEFAULT 1 CHECK (available_copies >= 0),
                price REAL NOT NULL DEFAULT 19.99,
                popularity_score INTEGER NOT NULL DEFAULT 50 CHECK (popularity_score BETWEEN 1 AND 100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS patrons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                patron_type TEXT NOT NULL DEFAULT 'Student' CHECK (patron_type IN ('Student', 'Faculty', 'Community')),
                borrow_limit INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Suspended', 'Inactive')),
                balance_fines REAL NOT NULL DEFAULT 0.00 CHECK (balance_fines >= 0.0),
                behavior_profile TEXT NOT NULL DEFAULT 'Typical' CHECK (behavior_profile IN ('Meticulous', 'Typical', 'Procrastinator', 'Forgetful')),
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                patron_id INTEGER NOT NULL REFERENCES patrons(id) ON DELETE CASCADE,
                loan_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Overdue', 'Returned', 'Lost')),
                fine_accrued REAL NOT NULL DEFAULT 0.00,
                fine_paid REAL NOT NULL DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                patron_id INTEGER NOT NULL REFERENCES patrons(id) ON DELETE CASCADE,
                reservation_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Ready', 'Fulfilled', 'Cancelled', 'Expired')),
                notified_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS fine_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patron_id INTEGER NOT NULL REFERENCES patrons(id) ON DELETE CASCADE,
                loan_id INTEGER REFERENCES loans(id) ON DELETE SET NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                payment_date TEXT NOT NULL,
                payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK (payment_method IN ('Cash', 'Card', 'Online', 'Waived')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS simulation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sim_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_name TEXT,
                summary TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            -- Indexes for quick search and lookups
            CREATE INDEX IF NOT EXISTS idx_books_category ON books(category);
            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
            CREATE INDEX IF NOT EXISTS idx_patrons_card ON patrons(card_number);
            CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
            CREATE INDEX IF NOT EXISTS idx_loans_patron ON loans(patron_id);
            CREATE INDEX IF NOT EXISTS idx_loans_book ON loans(book_id);
            CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);
            CREATE INDEX IF NOT EXISTS idx_events_date ON simulation_events(sim_date);
        """)

        # Default system configurations
        default_configs = {
            "current_sim_date": "2026-10-01",
            "fine_rate_per_day": "0.50",
            "loan_duration_student": "14",
            "loan_duration_faculty": "28",
            "loan_duration_community": "7",
            "simulation_speed": "normal",
            "simulation_paused": "1",
            "library_name": "Athenaeum Central Simulation Library"
        }

        for key, value in default_configs.items():
            cursor.execute("""
                INSERT OR IGNORE INTO system_config (key, value)
                VALUES (?, ?)
            """, (key, value))

    print(f"Database initialized successfully at: {DB_FILE}")

def get_system_config():
    """Returns the system configuration key-value dictionary."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM system_config")
        return {row["key"]: row["value"] for row in cursor.fetchall()}

def update_system_config(key, value):
    """Updates a single system configuration entry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_config (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))

if __name__ == "__main__":
    init_db(reset=True)
