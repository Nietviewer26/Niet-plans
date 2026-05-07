"""
database.py — SQLite persistence layer.
Uses Postgres-compatible DDL. All external-service types come from interfaces.py.
"""
from __future__ import annotations

import random
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).parent / "agency.db"


@contextmanager
def _conn():
    con = sqlite3.connect(str(_DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    industry    TEXT,
    brand_voice TEXT,
    target_audience TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ad_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform            TEXT    NOT NULL,
    external_account_id TEXT    NOT NULL,
    name                TEXT,
    connected_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    provider            TEXT    NOT NULL,
    external_account_id TEXT    NOT NULL,
    name                TEXT,
    connected_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name                TEXT    NOT NULL,
    objective           TEXT,
    channel             TEXT    NOT NULL,
    daily_budget_cents  INTEGER NOT NULL DEFAULT 0,
    status              TEXT    NOT NULL DEFAULT 'draft',
    external_id         TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    headline    TEXT,
    body        TEXT,
    cta         TEXT,
    image_url   TEXT,
    true_ctr    REAL    NOT NULL DEFAULT 0.02,
    true_cvr    REAL    NOT NULL DEFAULT 0.05,
    status      TEXT    NOT NULL DEFAULT 'active',
    weight      REAL    NOT NULL DEFAULT 1.0,
    external_id TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS metrics_daily (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id      INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    date            TEXT    NOT NULL,
    impressions     INTEGER NOT NULL DEFAULT 0,
    clicks          INTEGER NOT NULL DEFAULT 0,
    conversions     INTEGER NOT NULL DEFAULT 0,
    spend_cents     INTEGER NOT NULL DEFAULT 0,
    revenue_cents   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(variant_id, date)
);

CREATE TABLE IF NOT EXISTS generations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,
    prompt      TEXT,
    output      TEXT,
    model       TEXT,
    cost_cents  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_sends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    sent_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    recipients_count INTEGER NOT NULL DEFAULT 0,
    opens           INTEGER NOT NULL DEFAULT 0,
    clicks          INTEGER NOT NULL DEFAULT 0,
    external_id     TEXT
);

CREATE TABLE IF NOT EXISTS branding (
    client_id       INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    brand_name      TEXT,
    primary_color   TEXT    NOT NULL DEFAULT '#1F2937',
    accent_color    TEXT    NOT NULL DEFAULT '#10B981',
    logo_url        TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create schema and seed demo data if the clients table is empty."""
    with _conn() as con:
        con.executescript(_SCHEMA)

    with _conn() as con:
        row = con.execute("SELECT COUNT(*) AS c FROM clients").fetchone()
        if row["c"] > 0:
            return

        # Seed demo client
        con.execute(
            """
            INSERT INTO clients (name, industry, brand_voice, target_audience)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Demo Boutique Coffee Co.",
                "Specialty coffee, DTC",
                "Warm, knowledgeable, slightly nerdy. Talk about origin and roast "
                "like a pro but never condescend. UK English.",
                "Coffee enthusiasts aged 28–55, urban, willing to spend £15+ per bag for quality.",
            ),
        )
        client_id = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # Attach mock accounts
        meta_acct = f"act_mock_{uuid.uuid4().hex[:8]}"
        klav_acct = f"klaviyo_mock_{uuid.uuid4().hex[:8]}"
        con.execute(
            "INSERT INTO ad_accounts (client_id, platform, external_account_id, name) VALUES (?,?,?,?)",
            (client_id, "meta", meta_acct, "Demo Meta Ad Account"),
        )
        con.execute(
            "INSERT INTO email_accounts (client_id, provider, external_account_id, name) VALUES (?,?,?,?)",
            (client_id, "klaviyo", klav_acct, "Demo Klaviyo Account"),
        )


def list_clients() -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute("SELECT * FROM clients ORDER BY created_at DESC").fetchall()


def get_client(client_id: int) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()


def create_client(
    name: str,
    industry: str = "",
    brand_voice: str = "",
    target_audience: str = "",
) -> int:
    with _conn() as con:
        con.execute(
            "INSERT INTO clients (name, industry, brand_voice, target_audience) VALUES (?,?,?,?)",
            (name, industry, brand_voice, target_audience),
        )
        return con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def list_campaigns(client_id: int | None = None) -> list[sqlite3.Row]:
    with _conn() as con:
        if client_id is not None:
            return con.execute(
                "SELECT * FROM campaigns WHERE client_id = ? ORDER BY created_at DESC",
                (client_id,),
            ).fetchall()
        return con.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()


def list_variants(campaign_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM variants WHERE campaign_id = ? ORDER BY id",
            (campaign_id,),
        ).fetchall()


def get_branding(client_id: int) -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM branding WHERE client_id = ?", (client_id,)
        ).fetchone()
    if row:
        return dict(row)
    # Defaults
    return {
        "client_id": client_id,
        "brand_name": None,
        "primary_color": "#1F2937",
        "accent_color": "#10B981",
        "logo_url": None,
        "updated_at": None,
    }


def upsert_branding(
    client_id: int,
    brand_name: str | None,
    primary_color: str,
    accent_color: str,
    logo_url: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO branding (client_id, brand_name, primary_color, accent_color, logo_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                brand_name    = excluded.brand_name,
                primary_color = excluded.primary_color,
                accent_color  = excluded.accent_color,
                logo_url      = excluded.logo_url,
                updated_at    = excluded.updated_at
            """,
            (client_id, brand_name, primary_color, accent_color, logo_url, now),
        )


def record_generation(
    client_id: int,
    kind: str,
    prompt: str,
    output: str,
    model: str,
    cost_cents: int = 0,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO generations (client_id, kind, prompt, output, model, cost_cents)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, kind, prompt, output, model, cost_cents),
        )


def usage_summary(days: int = 30) -> dict:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT kind, COUNT(*) AS cnt, SUM(cost_cents) AS cost
            FROM generations
            WHERE created_at >= datetime('now', ? || ' days')
            GROUP BY kind
            """,
            (f"-{days}",),
        ).fetchall()

    total_count = sum(r["cnt"] for r in rows)
    total_cost = sum(r["cost"] or 0 for r in rows)
    by_kind = {r["kind"]: r["cnt"] for r in rows}
    return {
        "total_count": total_count,
        "total_cost_cents": total_cost,
        "by_kind": by_kind,
    }


def list_ad_accounts(client_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM ad_accounts WHERE client_id = ?", (client_id,)
        ).fetchall()


def list_email_accounts(client_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM email_accounts WHERE client_id = ?", (client_id,)
        ).fetchall()


def create_campaign(
    client_id: int,
    name: str,
    objective: str,
    channel: str,
    daily_budget_cents: int,
    status: str = "draft",
) -> int:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO campaigns (client_id, name, objective, channel, daily_budget_cents, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, name, objective, channel, daily_budget_cents, status),
        )
        return con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def update_campaign_external_id(campaign_id: int, external_id: str, status: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE campaigns SET external_id = ?, status = ? WHERE id = ?",
            (external_id, status, campaign_id),
        )


def create_variant(
    campaign_id: int,
    name: str,
    headline: str,
    body: str,
    cta: str,
    image_url: str | None = None,
    true_ctr: float = 0.02,
    true_cvr: float = 0.05,
    external_id: str | None = None,
) -> int:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO variants
                (campaign_id, name, headline, body, cta, image_url, true_ctr, true_cvr, external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (campaign_id, name, headline, body, cta, image_url, true_ctr, true_cvr, external_id),
        )
        return con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def update_variant_weight(variant_id: int, weight: float) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE variants SET weight = ? WHERE id = ?",
            (weight, variant_id),
        )


def update_variant_status(variant_id: int, status: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE variants SET status = ? WHERE id = ?",
            (status, variant_id),
        )


def get_campaign(campaign_id: int) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
