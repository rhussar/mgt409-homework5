"""Campus Customs shop tools. Run from the hw5 root using python mcp_server/server.py."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("CAMPUS_DB_PATH", str(ROOT / "data/campus_customs_new.db"))).resolve()
ORIGINAL = ROOT / "data/campus_customs.db"
if DB_PATH == ORIGINAL.resolve():
    raise RuntimeError("The MCP server cannot use the original database as its working copy.")
mcp = FastMCP("Campus Customs Operations")


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def rows(db, sql, params=()):
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def ticket_row(db, ticket_id):
    found = rows(db, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
    if not found:
        raise ValueError("Unknown ticket")
    return found[0]


@mcp.tool()
def read_ticket(ticket_id: int) -> dict:
    """Read an actual ticket, its shop date, and linked invoice or lease by id."""
    with database() as db:
        ticket = ticket_row(db, ticket_id)
        return {
            "ticket": ticket,
            "desk": rows(db, "SELECT * FROM desk")[0],
            "invoice": rows(db, "SELECT * FROM invoices WHERE id=?", (ticket["invoice_id"],)),
            "lease": rows(db, "SELECT * FROM leases WHERE id=?", (ticket["lease_id"],)),
        }


@mcp.tool()
def check_inventory(sku: str, size: str) -> dict:
    """Read stock and pricing for a SKU/size, plus actual vendors and unpaid invoices."""
    with database() as db:
        stock = rows(db, "SELECT * FROM inventory WHERE sku=? AND size=?", (sku, size))
        if not stock:
            raise ValueError("Unknown SKU/size; do not infer a zero stock record.")
        return {
            "inventory": stock[0],
            "pricing": rows(db, "SELECT * FROM pricing WHERE sku=?", (sku,)),
            "vendors": rows(db, "SELECT * FROM vendors ORDER BY id"),
            "unpaid_invoices": rows(db, "SELECT * FROM invoices WHERE status!='paid'"),
            "note": "Vendor specialties are evidence for a recommendation, not a confirmed SKU contract. No receipt or incoming stock is modeled.",
        }


@mcp.tool()
def financial_snapshot() -> dict:
    """Read cash, bills, leases, prices and payments; determine overdue items using desk.date_today."""
    with database() as db:
        snapshot = {name: rows(db, f"SELECT * FROM {name}") for name in (
            "desk", "cash_accounts", "invoices", "leases", "payments", "pricing", "vendors"
        )}
        if rows(db, "SELECT name FROM sqlite_master WHERE type='table' AND name='approval_requests'"):
            snapshot["prepared_approvals"] = rows(db, "SELECT * FROM approval_requests WHERE status='pending'")
        snapshot["time_context"] = {"business_today": snapshot["desk"][0]["date_today"], "note": "All payment and approval timestamps use the real execution clock. Do not use those timestamps to calculate business due dates. Rent approval advances next_due one calendar month from the approved obligation due date."}
        return snapshot


from operations import register
register(mcp, database, rows, ticket_row, DB_PATH, ORIGINAL)


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
