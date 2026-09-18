"""SQLite store for proposal decisions — ensures idempotent re-runs."""
import json
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH


def init_db(path: str = DB_PATH):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            key         TEXT PRIMARY KEY,
            ptype       TEXT,
            account_id  TEXT,
            slug        TEXT,
            payload     TEXT,
            status      TEXT DEFAULT 'pending',
            decided_at  TEXT,
            note        TEXT
        )
    """)
    con.commit()
    con.close()


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def upsert_proposal(proposal: dict):
    """Insert a new proposal as pending; skip if the key already exists (already decided)."""
    con = _connect()
    con.execute("""
        INSERT OR IGNORE INTO decisions (key, ptype, account_id, slug, payload, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (
        proposal["key"],
        proposal["ptype"],
        proposal.get("account_id") or "",
        proposal.get("slug") or "",
        json.dumps(proposal),
    ))
    con.commit()
    con.close()


def get_proposals(status: str = None) -> list[dict]:
    con = _connect()
    if status:
        rows = con.execute("SELECT payload, status FROM decisions WHERE status = ?", (status,)).fetchall()
    else:
        rows = con.execute("SELECT payload, status FROM decisions").fetchall()
    con.close()
    results = []
    for row in rows:
        p = json.loads(row["payload"])
        p["_db_status"] = row["status"]
        results.append(p)
    return results


def mark_decision(key: str, status: str, note: str = ""):
    con = _connect()
    con.execute(
        "UPDATE decisions SET status = ?, decided_at = ?, note = ? WHERE key = ?",
        (status, datetime.now(timezone.utc).isoformat(), note, key),
    )
    con.commit()
    con.close()


def counts() -> dict:
    con = _connect()
    rows = con.execute("SELECT status, COUNT(*) as n FROM decisions GROUP BY status").fetchall()
    con.close()
    return {row["status"]: row["n"] for row in rows}
