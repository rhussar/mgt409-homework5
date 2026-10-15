"""Transactional shop operations registered on the same FastMCP server."""
from __future__ import annotations

import calendar
import hmac
import json
import os
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


def register(mcp, database, rows, ticket_row, db_path, original):
    def now():
        return datetime.now(timezone.utc).isoformat()

    def cents(value):
        return int((Decimal(str(value)) * 100).quantize(Decimal("1")))

    def initialize():
        with database() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                kind TEXT NOT NULL, ref_id INTEGER, amount REAL NOT NULL CHECK(amount>0),
                description TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, decided_at TEXT, approved_by TEXT, payment_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS customer_drafts (
                ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id), recipient TEXT NOT NULL,
                subject TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ticket_decisions (
                ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id), decision TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ticket_quotes (
                ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id), quote_json TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id TEXT PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                vendor_id INTEGER NOT NULL REFERENCES vendors(id), sku TEXT NOT NULL, size TEXT NOT NULL,
                qty INTEGER NOT NULL CHECK(qty>0), amount REAL NOT NULL,
                estimated_arrival TEXT NOT NULL, status TEXT NOT NULL, payment_id INTEGER NOT NULL
            );
            ''')
    initialize()

    def next_month(value):
        due = date.fromisoformat(value)
        year, month = (due.year+1, 1) if due.month == 12 else (due.year, due.month+1)
        return due.replace(year=year, month=month, day=min(due.day, calendar.monthrange(year, month)[1])).isoformat()

    def state(db, ticket_id):
        ticket = ticket_row(db, ticket_id)
        result = {
            "ticket": ticket, "desk": rows(db, "SELECT * FROM desk")[0],
            "invoice": rows(db, "SELECT * FROM invoices WHERE id=?", (ticket["invoice_id"],)),
            "lease": rows(db, "SELECT * FROM leases WHERE id=?", (ticket["lease_id"],)),
            "approvals": rows(db, "SELECT * FROM approval_requests WHERE ticket_id=? ORDER BY created_at", (ticket_id,)),
            "drafts": rows(db, "SELECT * FROM customer_drafts WHERE ticket_id=?", (ticket_id,)),
            "decisions": rows(db, "SELECT * FROM ticket_decisions WHERE ticket_id=?", (ticket_id,)),
            "purchase_orders": rows(db, "SELECT * FROM purchase_orders WHERE ticket_id=?", (ticket_id,)),
            "quotes": [json.loads(r["quote_json"]) for r in rows(db, "SELECT * FROM ticket_quotes WHERE ticket_id=?", (ticket_id,))],
        }
        timing = {"business_today": result["desk"]["date_today"],
            "audit_clock_note": "paid_at, created_at, decided_at and updated_at are actual execution timestamps. Use business_today for every due-date or lead-time calculation.",
            "rent_rule": "Approving rent automatically advances lease.next_due one calendar month from the approved request details.due_date. Those dates should differ."}
        transitions = []
        for approval in result["approvals"]:
            if approval["kind"] == "rent" and approval["status"] == "approved":
                previous_due = json.loads(approval["details"])["due_date"]
                current_due = result["lease"][0]["next_due"]
                transitions.append({"paid_obligation_due":previous_due,"expected_next_due":next_month(previous_due),"current_lease_next_due":current_due,"transition_matches":next_month(previous_due)==current_due})
        timing["rent_transitions"] = transitions
        result["timing"] = timing
        return result

    @mcp.tool()
    def ticket_state(ticket_id: int) -> dict:
        """Read a ticket with persisted approvals, decisions, draft messages and incoming orders."""
        with database() as db:
            return state(db, ticket_id)

    @mcp.tool()
    def list_tickets() -> dict:
        """Read all tickets, their approvals and drafts, and current checking cash."""
        with database() as db:
            return {"desk": rows(db, "SELECT * FROM desk")[0],
                    "tickets": [state(db, t["id"]) for t in rows(db, "SELECT id FROM tickets ORDER BY id")],
                    "cash_accounts": rows(db, "SELECT * FROM cash_accounts"),
                    "payments": rows(db, "SELECT * FROM payments ORDER BY id")}

    def prepare(db, ticket_id, kind, ref_id, amount, description, details):
        if ticket_row(db, ticket_id)["status"] == "resolved":
            return {"ok": False, "error": "Ticket already resolved"}
        previous = rows(db, "SELECT * FROM approval_requests WHERE ticket_id=? AND kind=? AND ref_id IS ? AND details=? AND status IN ('pending','approved')", (ticket_id, kind, ref_id, json.dumps(details, sort_keys=True)))
        if previous:
            return {"ok": True, "request": previous[0], "idempotent": True}
        balance = cents(rows(db, "SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"])
        reserved = sum(cents(r["amount"]) for r in rows(db, "SELECT amount FROM approval_requests WHERE status='pending'"))
        if cents(amount) > balance - reserved:
            return {"ok": False, "error": "Insufficient unreserved cash", "balance": balance/100, "pending_reserved": reserved/100, "requested": amount}
        request_id = str(uuid.uuid4())
        db.execute("INSERT INTO approval_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            request_id, ticket_id, kind, ref_id, amount, description, json.dumps(details, sort_keys=True),
            "pending", now(), None, None, None))
        return {"ok": True, "request": rows(db, "SELECT * FROM approval_requests WHERE id=?", (request_id,))[0], "note": "Prepared only. Cash unchanged. Human approval required."}

    @mcp.tool()
    def prepare_payment(ticket_id: int, kind: str, ref_id: int, reason: str) -> dict:
        """Prepare an invoice or rent payment at the database amount. Does not pay. kind is invoice or rent."""
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            t = ticket_row(db, ticket_id)
            if kind == "invoice":
                if t["invoice_id"] != ref_id:
                    raise ValueError("Invoice does not belong to this ticket")
                bill = rows(db, "SELECT * FROM invoices WHERE id=?", (ref_id,))[0]
                if bill["status"] == "paid":
                    return {"ok": True, "already_paid": True}
                return prepare(db, ticket_id, kind, ref_id, bill["amount"], reason, {"vendor_id": bill["vendor_id"]})
            if kind == "rent":
                if t["lease_id"] != ref_id:
                    raise ValueError("Lease does not belong to this ticket")
                lease = rows(db, "SELECT * FROM leases WHERE id=?", (ref_id,))[0]
                paid = rows(db, "SELECT * FROM approval_requests WHERE ticket_id=? AND kind='rent' AND status='approved'", (ticket_id,))
                if paid:
                    return {"ok": True, "already_paid": True, "request": paid[0]}
                return prepare(db, ticket_id, kind, ref_id, lease["monthly_rent"], reason, {"due_date": lease["next_due"], "landlord": lease["landlord"]})
            raise ValueError("Use invoice or rent; purchase uses prepare_purchase")

    @mcp.tool()
    def prepare_purchase(ticket_id: int, quantity: int, vendor_id: int, reason: str) -> dict:
        """Prepare a shortfall purchase at modeled unit_cost; refuse unpaid vendors or insufficient cash. Never receive stock."""
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            t = ticket_row(db, ticket_id)
            stock = rows(db, "SELECT * FROM inventory WHERE sku=? AND size=?", (t["sku"], t["size"]))
            if not stock or quantity < 1 or quantity > max(0, t["qty"] - stock[0]["qty"]):
                raise ValueError("Purchase quantity must be within the actual ticket shortfall")
            vendor = rows(db, "SELECT * FROM vendors WHERE id=?", (vendor_id,))
            if not vendor or "apparel" not in vendor[0]["specialty"].lower():
                raise ValueError("No database evidence that this vendor can supply this apparel")
            unpaid = rows(db, "SELECT * FROM invoices WHERE vendor_id=? AND status!='paid'", (vendor_id,))
            if unpaid:
                return {"ok": False, "error": "Vendor blocked by unpaid invoice", "invoices": unpaid}
            price = rows(db, "SELECT * FROM pricing WHERE sku=?", (t["sku"],))[0]
            amount = cents(price["unit_cost"]) * quantity / 100
            details = {"vendor_id": vendor_id, "sku": t["sku"], "size": t["size"], "qty": quantity, "unit_cost": price["unit_cost"], "pricing_basis": "database modeled cost; not an external vendor quote"}
            return prepare(db, ticket_id, "purchase", vendor_id, amount, reason, details)

    @mcp.tool()
    def quote_offer(ticket_id: int, quantity: int, unit_price: float) -> dict:
        """Compute and save exact offer economics from database stock/cost/list price. No sale, cash or stock change."""
        with database() as db:
            t = ticket_row(db, ticket_id)
            stock = rows(db, "SELECT * FROM inventory WHERE sku=? AND size=?", (t["sku"], t["size"]))
            price = rows(db, "SELECT * FROM pricing WHERE sku=?", (t["sku"],))
            if not stock or not price or quantity < 1 or quantity > min(stock[0]["qty"], t["qty"]):
                raise ValueError("Quote only quantities supported by exact-size stock and this request")
            raw = Decimal(str(unit_price)) * 100
            if raw != raw.to_integral_value() or unit_price <= 0:
                raise ValueError("Use a positive unit price with at most two decimal places")
            cost, listed, offer = cents(price[0]["unit_cost"]), cents(price[0]["list_price"]), cents(unit_price)
            quote = {"ticket_id": ticket_id, "sku": t["sku"], "size": t["size"], "quantity": quantity,
                "unit_price": offer/100, "list_price": listed/100, "unit_cost": cost/100,
                "discount_percent": round((listed-offer)/listed*100, 2),
                "gross_margin_percent": round((offer-cost)/offer*100, 2),
                "unit_gross_profit": (offer-cost)/100, "total_if_accepted": offer*quantity/100,
                "existing_stock_cost_basis": cost*quantity/100, "total_gross_profit": (offer-cost)*quantity/100,
                "available_qty": stock[0]["qty"], "unfilled_requested_qty": t["qty"]-quantity,
                "stock_shortfall": max(0,t["qty"]-stock[0]["qty"]),
                "modeled_full_shortfall_purchase_cost": max(0,t["qty"]-stock[0]["qty"])*cost/100,
                "cash_change_now": 0,
                "note": "Proposed offer only. Existing stock cost basis is not a new payment; no revenue or stock reservation is recorded."}
            db.execute("INSERT INTO ticket_quotes VALUES (?,?,?) ON CONFLICT(ticket_id) DO UPDATE SET quote_json=excluded.quote_json,updated_at=excluded.updated_at",(ticket_id,json.dumps(quote),now()))
            return quote

    @mcp.tool()
    def save_decision(ticket_id: int, decision: str) -> dict:
        """Save a business decision for a ticket. Does not pay, sell, ship, or change inventory."""
        with database() as db:
            ticket_row(db, ticket_id)
            db.execute("INSERT INTO ticket_decisions VALUES (?,?,?) ON CONFLICT(ticket_id) DO UPDATE SET decision=excluded.decision, updated_at=excluded.updated_at", (ticket_id, decision[:10000], now()))
        return {"ok": True, "decision": decision}

    @mcp.tool()
    def save_customer_draft(ticket_id: int, subject: str, body: str) -> dict:
        """Store a draft addressed to the ticket requester. No message is ever sent."""
        with database() as db:
            t = ticket_row(db, ticket_id)
            db.execute("INSERT INTO customer_drafts VALUES (?,?,?,?,?) ON CONFLICT(ticket_id) DO UPDATE SET subject=excluded.subject,body=excluded.body,updated_at=excluded.updated_at", (ticket_id, t["requester"], subject[:200], body[:10000], now()))
        return {"ok": True, "recipient": t["requester"], "subject": subject, "body": body, "sent": False}

    @mcp.tool()
    def resolve_ticket(ticket_id: int, outcome: str) -> dict:
        """Close operational handling after required payments and drafts exist. Resolution never means goods received or customers contacted."""
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            t = ticket_row(db, ticket_id)
            if t["status"] == "resolved":
                db.execute("UPDATE tickets SET notes=? WHERE id=?", (t["notes"].split("\nResolution:")[0] + "\nResolution: " + outcome[:5000], ticket_id))
                return {"ok": True, "idempotent": True, "ticket": ticket_row(db,ticket_id)}
            if rows(db, "SELECT id FROM approval_requests WHERE ticket_id=? AND status='pending'", (ticket_id,)):
                return {"ok": False, "error": "Human approval still pending"}
            if not rows(db, "SELECT * FROM ticket_decisions WHERE ticket_id=?", (ticket_id,)):
                return {"ok": False, "error": "Save an explicit business decision first"}
            if t["invoice_id"] and rows(db, "SELECT status FROM invoices WHERE id=?", (t["invoice_id"],))[0]["status"] != "paid":
                return {"ok": False, "error": "Linked invoice remains unpaid"}
            if t["lease_id"] and not rows(db, "SELECT id FROM approval_requests WHERE ticket_id=? AND kind='rent' AND status='approved'", (ticket_id,)):
                return {"ok": False, "error": "Rent not approved and paid"}
            if t["type"] in ("customer_order", "price_override") and not rows(db, "SELECT * FROM customer_drafts WHERE ticket_id=?", (ticket_id,)):
                return {"ok": False, "error": "Customer draft required"}
            db.execute("UPDATE tickets SET status='resolved',notes=COALESCE(notes,'') || ? WHERE id=?", ("\nResolution: " + outcome[:5000], ticket_id))
            return {"ok": True, "ticket": ticket_row(db, ticket_id)}

    def authorize(token):
        expected = os.getenv("HUMAN_APPROVAL_TOKEN", "")
        if not expected or not hmac.compare_digest(token, expected):
            raise ValueError("Human route authorization required; agents cannot approve or reset")

    @mcp.tool()
    def decide_approval(request_id: str, approve: bool, approved_by: str, authorization: str) -> dict:
        """Human backend route only. Atomically decide a prepared request; never exposed to agents. Requires private route authorization."""
        authorize(authorization)
        if not approved_by.strip():
            raise ValueError("Approver required")
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            found = rows(db, "SELECT * FROM approval_requests WHERE id=?", (request_id,))
            if not found:
                raise ValueError("Unknown approval request")
            req = found[0]
            if req["status"] != "pending":
                return {"ok": True, "idempotent": True, "request": req}
            if not approve:
                db.execute("UPDATE approval_requests SET status='rejected',decided_at=?,approved_by=? WHERE id=?", (now(), approved_by, request_id))
                return {"ok": True, "status": "rejected"}
            detail = json.loads(req["details"])
            if req["kind"] == "purchase" and rows(db, "SELECT id FROM invoices WHERE vendor_id=? AND status!='paid'", (detail["vendor_id"],)):
                return {"ok": False, "error": "Vendor now blocked by an unpaid invoice"}
            if req["kind"] == "invoice":
                bill = rows(db, "SELECT * FROM invoices WHERE id=?", (req["ref_id"],))[0]
                if bill["status"] == "paid" or cents(bill["amount"]) != cents(req["amount"]):
                    return {"ok": False, "error": "Invoice changed; create a fresh request"}
            if req["kind"] == "rent":
                lease = rows(db, "SELECT * FROM leases WHERE id=?", (req["ref_id"],))[0]
                if lease["next_due"] != detail["due_date"] or cents(lease["monthly_rent"]) != cents(req["amount"]):
                    return {"ok": False, "error": "Lease changed; create a fresh request"}
            cash = rows(db, "SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"]
            if cents(cash) < cents(req["amount"]):
                return {"ok": False, "error": "Insufficient cash; payment refused", "balance": cash}
            today = rows(db, "SELECT date_today FROM desk")[0]["date_today"]
            new_cash = (cents(cash) - cents(req["amount"]))/100
            db.execute("UPDATE cash_accounts SET balance=?,date=? WHERE name='checking'", (new_cash, today))
            payment = db.execute("INSERT INTO payments(kind,ref_id,amount,account,paid_at,approved_by) VALUES (?,?,?,'checking',?,?)", (req["kind"], req["ref_id"], req["amount"], now(), approved_by))
            pid = payment.lastrowid
            if req["kind"] == "invoice":
                db.execute("UPDATE invoices SET status='paid' WHERE id=?", (req["ref_id"],))
            elif req["kind"] == "rent":
                db.execute("UPDATE leases SET next_due=? WHERE id=?", (next_month(detail["due_date"]), req["ref_id"]))
            elif req["kind"] == "purchase":
                lead = rows(db, "SELECT lead_days FROM vendors WHERE id=?", (detail["vendor_id"],))[0]["lead_days"]
                arrival = (date.fromisoformat(today)+timedelta(days=lead)).isoformat()
                db.execute("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?,?,?,?)", (request_id, req["ticket_id"], detail["vendor_id"], detail["sku"], detail["size"], detail["qty"], req["amount"], arrival, "ordered_not_received", pid))
            db.execute("UPDATE approval_requests SET status='approved',decided_at=?,approved_by=?,payment_id=? WHERE id=?", (now(), approved_by, pid, request_id))
            return {"ok": True, "status": "approved", "payment_id": pid, "amount": req["amount"], "balance": new_cash, "ticket_id": req["ticket_id"]}

    @mcp.tool()
    def reset_shop(authorization: str) -> dict:
        """Human backend route only. Restore the working DB from the untouched original; audit file is preserved."""
        authorize(authorization)
        # Backend excludes all active runs before this operation.
        shutil.copyfile(original, db_path)
        initialize()
        return {"ok": True, "note": "Working database reset. Original and append-only audit history preserved."}
