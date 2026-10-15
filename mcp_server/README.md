# Campus Customs MCP Server

FastMCP exposes shop facts and transactional operations over stdio. `server.py` defines the three initial read tools; `operations.py` registers the workflow tools on the same server. All reads and writes use `data/campus_customs_new.db`, or the explicit `CAMPUS_DB_PATH` test override. Pointing at the original database is refused.

From the Homework 5 root with dependencies installed:

```bash
source .venv/bin/activate
python mcp_server/server.py
```

Stdio servers wait for a client. The backend starts its own managed subprocess, so a separate manually started process is not needed for the dashboard. `.mcp.json` and `.codex/config.toml` provide project-local client configuration. Launch the client from this folder. Check the three original tools with `python scripts/mcp_smoke.py`.

| Tool | Tables and operation |
| --- | --- |
| read_ticket | Read tickets, desk, linked invoices and leases. |
| check_inventory | Read inventory, pricing, vendors and unpaid invoices for an exact SKU/size. |
| financial_snapshot | Read desk, cash_accounts, invoices, leases, payments, pricing, vendors and pending approvals. |
| ticket_state | Read a ticket's business links, approval_requests, customer_drafts, ticket_decisions and purchase_orders. |
| list_tickets | Read all ticket states, checking cash and payments for the board. |
| prepare_payment | Read linked invoice/lease amount and cash; insert an approval_requests row without paying. |
| prepare_purchase | Read stock shortfall, pricing, vendor eligibility and cash; insert a request without receiving stock. |
| quote_offer | Read stock, pricing and ticket quantity; save exact proposed discount and margin calculations in ticket_quotes without spending cash. |
| save_decision | Persist the Boss decision in ticket_decisions. |
| save_customer_draft | Persist a draft to the ticket requester in customer_drafts; never send. |
| resolve_ticket | Validate prerequisites and update ticket status/notes. |
| decide_approval | Private human backend tool: atomically update approvals, cash, payment history and the linked invoice/lease/order. |
| reset_shop | Private human backend tool: copy the untouched original over the working DB, then initialize workflow tables. |

The final two tools require a capability generated inside the backend. They are never registered as agent tools, and are disabled in the project's Codex connection. A standalone stdio client without that capability cannot execute them. Approval is idempotent and rechecks sufficient cash and relevant facts under a SQLite write lock. No payment can make checking negative.

The five workflow tables exist only in the working copy. Purchase orders are incoming, never a stock receipt. No arbitrary SQL, email, customer charging, bank API, vendor-contact or external network tool is exposed. See `output/harness.md` for per-tool table mappings, role permissions and exact limits.
