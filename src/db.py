import sqlite3
from datetime import date

import pymysql

from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=True,
        connect_timeout=5,
    )


# ---------------------------------------------------------------------------
# SQLite local backup
# ---------------------------------------------------------------------------

def init_local_sqlite(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    conn.execute('CREATE TABLE IF NOT EXISTS plants (name TEXT PRIMARY KEY, category TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS eaten_log (id INTEGER PRIMARY KEY, log_date TEXT, plant_name TEXT)')
    conn.close()


def backup_to_sqlite(sqlite_path):
    """Pull the full remote DB into the local SQLite backup. Safe to run on a daemon thread."""
    try:
        with get_db_connection() as remote:
            with remote.cursor() as cur:
                cur.execute("SELECT name, category FROM plants")
                plants = cur.fetchall()
                cur.execute("SELECT id, log_date, plant_name FROM eaten_log")
                logs = cur.fetchall()

        conn = sqlite3.connect(sqlite_path)
        conn.execute("DELETE FROM plants")
        conn.execute("DELETE FROM eaten_log")
        conn.executemany("INSERT INTO plants VALUES (?,?)", plants)
        conn.executemany(
            "INSERT INTO eaten_log VALUES (?,?,?)",
            [
                (
                    l[0],
                    l[1].isoformat() if hasattr(l[1], 'isoformat') else l[1],
                    l[2],
                )
                for l in logs
            ],
        )
        conn.commit()
        conn.close()
        print("Sync complete.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_all_plants(sqlite_path):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name, category FROM plants ORDER BY name")
                return cur.fetchall()
    except Exception:
        conn = sqlite3.connect(sqlite_path)
        data = conn.execute("SELECT name, category FROM plants ORDER BY name").fetchall()
        conn.close()
        return data


def fetch_ui_data(sqlite_path, tracking_date, start_date):
    """
    Fetch all data needed to refresh the UI.
    Returns (weekly_data, daily_data, heatmap_total, heatmap_distinct).
    Safe to call on a background thread.
    """
    from datetime import timedelta

    anchor = tracking_date
    mon = anchor - timedelta(days=anchor.weekday())
    sun = mon + timedelta(days=6)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT plant_name, COUNT(*) FROM eaten_log "
                    "WHERE log_date BETWEEN %s AND %s GROUP BY plant_name",
                    (mon, sun),
                )
                weekly = cur.fetchall()

                cur.execute(
                    "SELECT log_date, plant_name, COUNT(*) FROM eaten_log "
                    "WHERE log_date BETWEEN %s AND %s GROUP BY log_date, plant_name",
                    (mon, sun),
                )
                daily = cur.fetchall()

                cur.execute(
                    "SELECT log_date, COUNT(*) FROM eaten_log "
                    "WHERE log_date >= %s GROUP BY log_date",
                    (start_date,),
                )
                heatmap_total = {r[0].isoformat(): r[1] for r in cur.fetchall()}

                cur.execute(
                    "SELECT log_date, COUNT(DISTINCT plant_name) FROM eaten_log "
                    "WHERE log_date >= %s GROUP BY log_date",
                    (start_date,),
                )
                heatmap_distinct = {r[0].isoformat(): r[1] for r in cur.fetchall()}

        return weekly, daily, heatmap_total, heatmap_distinct

    except Exception:
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()

        weekly = cur.execute(
            "SELECT plant_name, COUNT(*) FROM eaten_log "
            "WHERE log_date BETWEEN ? AND ? GROUP BY plant_name",
            (mon.isoformat(), sun.isoformat()),
        ).fetchall()

        daily = [
            (date.fromisoformat(r[0]), r[1], r[2])
            for r in cur.execute(
                "SELECT log_date, plant_name, COUNT(*) FROM eaten_log "
                "WHERE log_date BETWEEN ? AND ? GROUP BY log_date, plant_name",
                (mon.isoformat(), sun.isoformat()),
            ).fetchall()
        ]

        heatmap_total = {
            r[0]: r[1]
            for r in cur.execute(
                "SELECT log_date, COUNT(*) FROM eaten_log "
                "WHERE log_date >= ? GROUP BY log_date",
                (start_date.isoformat(),),
            ).fetchall()
        }

        heatmap_distinct = {
            r[0]: r[1]
            for r in cur.execute(
                "SELECT log_date, COUNT(DISTINCT plant_name) FROM eaten_log "
                "WHERE log_date >= ? GROUP BY log_date",
                (start_date.isoformat(),),
            ).fetchall()
        }

        conn.close()
        return weekly, daily, heatmap_total, heatmap_distinct


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def save_plant_log(sqlite_path, plant_name, date_str):
    """Insert a single eaten_log entry. Falls back to SQLite on failure."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO eaten_log (log_date, plant_name) VALUES (%s, %s)",
                    (date_str, plant_name),
                )
    except Exception:
        conn = sqlite3.connect(sqlite_path)
        conn.execute(
            "INSERT INTO eaten_log (log_date, plant_name) VALUES (?, ?)",
            (date_str, plant_name),
        )
        conn.commit()
        conn.close()


def delete_log_entry(lid):
    """Delete a single eaten_log row by id."""
    try:
        with get_db_connection() as conn:
            conn.cursor().execute("DELETE FROM eaten_log WHERE id=%s", (lid,))
    except Exception:
        pass


def add_plant(name, category):
    """Insert a new plant species. Silently ignores duplicates."""
    try:
        with get_db_connection() as conn:
            conn.cursor().execute("INSERT IGNORE INTO plants VALUES (%s, %s)", (name, category))
    except Exception:
        pass


def remove_plant(name):
    """Delete a plant and all its log entries."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM eaten_log WHERE plant_name=%s", (name,))
                cur.execute("DELETE FROM plants WHERE name=%s", (name,))
    except Exception:
        pass


def get_log_entries_for_date(sqlite_path, date_str):
    """Return [(id, plant_name), ...] for the given date."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, plant_name FROM eaten_log WHERE log_date=%s", (date_str,)
                )
                return cur.fetchall()
    except Exception:
        conn = sqlite3.connect(sqlite_path)
        items = conn.execute(
            "SELECT id, plant_name FROM eaten_log WHERE log_date=?", (date_str,)
        ).fetchall()
        conn.close()
        return items