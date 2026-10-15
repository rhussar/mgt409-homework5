# Campus Customs Operations Harness

## Database

The original database is preserved. Tools use `data/campus_customs_new.db`. The shop date is 2026-08-31, from `desk.date_today`.

| Table | Fields |
| --- | --- |
| `cash_accounts` | name, balance, date |
| `desk` | date_today, notes |
| `inventory` | sku, name, size, qty, location |
| `invoices` | id, vendor_id, amount, due_date, status, description |
| `leases` | id, space_name, landlord, monthly_rent, next_due, notes |
| `payments` | id, kind, ref_id, amount, account, paid_at, approved_by |
| `pricing` | sku, unit_cost, list_price |
| `tickets` | id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at |
| `vendors` | id, name, specialty, lead_days |

## Initial MCP tools

| Tool | Tables | Ticket and purpose |
| --- | --- | --- |
| read_ticket | tickets, desk, invoices, leases | 101: connects the out-of-stock tee request to invoice 501, rather than treating the request as a sale in isolation. |
| check_inventory | inventory, pricing, vendors, invoices | 103: reveals only 8 medium hoodies against a request for 20 and provides price/cost evidence for a counteroffer. |
| financial_snapshot | desk, cash_accounts, invoices, leases, payments, pricing, vendors | 102: compares the $2,400 rent due September 2 with $3,400 checking and the competing $840 overdue vendor bill. |

## Why the tables matter

| Table | Use in this shop |
| --- | --- |
| desk | Supplies the business date. August 28 is overdue relative to August 31; the machine clock is irrelevant to this calculation. |
| tickets | Connects each request to exact SKU/size, invoice or lease, and records operational resolution. |
| inventory | Gives size-specific available quantities. Medium hoodies have 8 units, not the total across sizes. |
| pricing | Supplies cost and list price for gross-margin calculations and modeled purchase costs. |
| vendors | Supplies specialties and lead days. A vendor recommendation is not a confirmed external quote. |
| invoices | Tracks the $840 reprint bill and whether a vendor is blocked from shipping. |
| leases | Supplies the $2,400 monthly rent and next due date; payment advances that date by one month. |
| cash_accounts | Checking is the sole modeled cash source. No negative cash or customer revenue is permitted. |
| payments | Permanent record of amount, reference, account, payment time and self-attested human approver. |

The working copy gains `approval_requests` (prepared amount, linked ticket, kind/reference, description/details, state, times, approver and payment link), `customer_drafts` (recipient, subject, body, timestamp per ticket), `ticket_decisions` (decision and timestamp per ticket), `ticket_quotes` (ticket, calculated quote JSON and update time), and `purchase_orders` (vendor/SKU/size/quantity, modeled cost, estimated arrival, incoming status and payment link). These keep workflow state separate from the original business facts while staying in the same MCP-owned database. See `mcp_server/operations.py` for their full field definitions.

## Architecture

The React board calls FastAPI. The backend owns one FastMCP stdio client that starts `mcp_server/server.py` as a subprocess. All five PydanticAI agents use that same protocol connection through a small typed `shop_tool` adapter. The adapter exposes a role-specific enum of permitted writes in the tool schema and validates role and ticket scope again in code; it contains no SQL or alternative shop operations. The human routes also call MCP for payment execution and reset.

Boss routes the ticket. Every agent has a `delegate(target, task)` tool supporting every other role. The model selects collaborators; no code hardcodes a specialist chain for ticket 101, 102 or 103. The dependency path prevents delegating to an ancestor, while depth and invocation limits stop loops. Specialists return structured reports to their caller. Boss alone saves the final decision and resolves the ticket. Accounting prepares payment requests; Customer Service persists drafts.

| Agent | Responsibility | Typical evidence |
| --- | --- | --- |
| Boss | Choose collaborators, decide price exceptions and next steps, persist decisions, close operational handling | Ticket state and specialist reports |
| Inventory | Exact stock/size, shortfall, vendor specialty and shipping block | inventory, pricing, vendors, invoices |
| Accounting | Cash, outstanding obligations, gross margin, payment/purchase preparation | cash_accounts, invoices, leases, pricing, payments |
| Facilities | Lease, landlord, business-date timing, verification after rent | leases, desk, payments |
| Customer Service | Accurate customer drafts, clear limitations and conditional timing | Ticket state, decisions and specialist evidence |

Each role loads its own file in `backend/prompts/`. Shared instructions add the shop rules and MCP tool contracts. All model calls use `gpt-6-luna` through the Portkey OpenAI-compatible endpoint with `PORTKEY_API_KEY`. Tool calls require `openai_reasoning_effort='none'` on the configured Chat Completions route; a real initial provider error is retained in the audit. There is no fallback model. Private reasoning is not collected.

## Complete MCP tool list

| Tool | Reads | Writes | Purpose |
| --- | --- | --- | --- |
| read_ticket | tickets, desk, linked invoices/leases | — | Original ticket and links |
| check_inventory | inventory, pricing, vendors, invoices | — | Exact-size stock, costs and vendor evidence |
| financial_snapshot | desk, cash_accounts, invoices, leases, payments, pricing, vendors, pending approval_requests | — | Cash, commitments, margins and timing |
| ticket_state | tickets, desk, invoices, leases, approval_requests, customer_drafts, ticket_decisions, purchase_orders | — | Resume from persisted evidence after approval |
| list_tickets | Same ticket-state tables plus cash_accounts/payments | — | Board snapshot and evidence export |
| prepare_payment | tickets, invoices or leases, cash_accounts, approval_requests | approval_requests | Prepare authoritative invoice/rent amount and reserve pending cash; never pay |
| prepare_purchase | tickets, inventory, pricing, vendors, invoices, cash_accounts, approval_requests | approval_requests | Prepare a quantity within the shortfall; refuse blocked vendor or insufficient unreserved cash |
| quote_offer | tickets, inventory, pricing | ticket_quotes | Compute exact discount, margin, stock-supported quantity and hypothetical totals with no cash change |
| save_decision | tickets | ticket_decisions | Persist Boss's business decision |
| save_customer_draft | tickets | customer_drafts | Save a draft to the ticket requester; no external sending |
| resolve_ticket | tickets, approval_requests, invoices, ticket_decisions, customer_drafts | tickets | Close only after required approved payment, decision and draft exist |
| decide_approval | approval_requests, invoices, leases, vendors, cash_accounts, desk | approval_requests, payments, cash_accounts; invoices or leases or purchase_orders | Human-only transaction; idempotent and guarded by a private capability |
| reset_shop | original database file | working database file, initializes workflow tables | Human-only reset; refuses to run alongside an active team |

Agents receive only the ten named shop tools in their adapter (all except `list_tickets`, `decide_approval`, `reset_shop`). The first three are tested in `output/mcp_smoke.json` through actual MCP transport. `output/mcp_smoke_initial.json` preserves the initial pre-payment results; `output/mcp_smoke.json` repeats the three calls against the final working database and matches its current values. Project-local `.mcp.json` and `.codex/config.toml` are included. `codex mcp get campus-customs --json` recognizes the enabled stdio configuration; live protocol calls are independently evidenced by the smoke test and agent audit.

## Human approval and money

Payment preparation inserts a pending request at the amount from the invoice or lease. It changes no cash. Pending requests reserve available cash to avoid oversubscription. Purchase amounts use the database unit cost multiplied by the approved shortfall quantity; that basis is identified as a model assumption, not an external quote.

The private `decide_approval` tool is excluded from agent tools and disabled in the project Codex connection. It requires a random capability created inside the backend and passed only to its MCP subprocess. That capability is absent from prompts, browser code, evidence and logs. The human dashboard route passes it only after the operator confirms the exact prepared request. The approver name is a local, self-attested audit label rather than production authentication.

The server takes a SQLite write lock, checks the request is still pending, rechecks cash and relevant invoice/lease/vendor facts, then updates cash and records the payment in the same transaction. Replaying an approved request returns its prior state without another charge. A rejected request leaves cash unchanged. An invoice payment marks the invoice paid. Rent advances `leases.next_due` by one month. A purchase creates an `ordered_not_received` record with estimated arrival based on `desk.date_today` and vendor lead days; it does not increase available inventory.

## API routes

| Method and URL | Behavior |
| --- | --- |
| GET /health | Backend model and MCP connection status |
| GET /api/desk | Tickets, approvals, drafts, payments, cash, run statuses and current session |
| GET /api/tickets | All three ticket records and persisted workflow state |
| POST /api/tickets/{ticket_id}/run | Start/continue the real team; returns 202 while it works |
| GET /api/events?after=N&ticket_id=ID | Public agent/tool events newer than the cursor, optionally for one ticket |
| POST /api/tickets/{ticket_id}/review | Review an existing decision against tools, preserving original and corrected audit events |
| POST /api/approvals/{request_id}/decide | Human approve/reject request; actual cash change occurs through guarded MCP |
| GET /api/cash | Current checking and payment history from MCP |
| POST /api/reset | Restore working copy after explicit reset confirmation; preserve audit and Expected plans |
| POST /api/export | Refresh actual ticket evidence, cash reconciliation and reflection draft |

Only one team run is active at a time. A pending human decision pauses the team; Continue ticket is explicit after a payment decision. Invalid duplicate starts and reset attempts during a run return 409. Mutating routes require the local action header and reject other browser origins. CORS allows only localhost/127.0.0.1 port 5173. This is a local simulation and must not be exposed as a production payment service.

## Structured models and audit

`AgentReport` contains a public summary, status, evidence list and recommendations, so callers receive comparable outputs rather than free-form guesses. `Role` restricts delegation targets to the five roles. `ApprovalDecision` validates the human decision and label. `ResetRequest` requires an explicit reset phrase. `AuditEvent` has a sequence ID, UTC wall-clock timestamp, shop session, run, ticket, agent, event, summary, optional tool/arguments/result and stop reason. Audit timestamps reflect actual execution; business due dates use the separate shop date.

Every model loop's tool-selection/output step is recorded, along with real tool calls and results, delegations and returns, reports, failures and human decisions. The public summary contains selected actions and returned facts, never private chain-of-thought. JSON is maintained as an append-only logical array, saved atomically after each append. Resets add a new session event rather than clearing the file. Reports filter to the current session so failed setup attempts and earlier test sessions remain auditable without being confused with final results.

`output/session.json` preserves the original starting balance and run/session metadata across backend restarts and cloning. It contains no secret. That lets graders launch the app on the submitted working database without losing the original cash baseline or overwriting evidence with a new guessed start value.

## Limits and safeguards

| Limit or guardrail | Value or behavior |
| --- | --- |
| Model | Fixed gpt-6-luna through Portkey for every agent |
| Active ticket teams | 1 |
| Whole-team wall time | 600 seconds |
| Model steps per individual agent invocation | At most 12 tool/output-selection steps |
| Delegation nesting | At most 4 levels including the current role; no ancestor cycles |
| Agent invocations per team run | At most 14 |
| Shared requests per team run | 45 |
| Shared successful tool calls | 90 |
| Shared total tokens | 100,000 |
| Model output cap | 1,800 tokens per request |
| Model request timeout/retries | 60 seconds, at most 1 HTTP retry; 1 schema/tool retry |
| Money | Positive authoritative amounts, integer-cent arithmetic, no negative balances, atomic updates, idempotent approvals |
| Vendor block | Checked at purchase preparation and again at payment |
| Stock | No receipt or fulfillment invented; incoming purchases do not increase stock |
| External communication | No email, vendor calls, checkout or outgoing-message tools |
| Data scope | Parameterized SQL; no arbitrary SQL tool; original DB path refused for working writes |
| Prompt injection | Ticket text/tool data is evidence, never instructions; no arbitrary execution or networking tools for agents |
| Secrets | Environment variable only; never embedded in browser, output files or configuration |
| Drafts and offers | Not sent, accepted, reserved, sold or counted as cash |
| Failure | Error retained in audit and visible on board; no mock output or model substitution |

## Evidence and evaluation

Expected plans were saved in `output/expected_plans.json` before the first agent run. `output/desk_tickets.html` preserves those plans, builds Actual sections from real agent events and persisted decisions, and itemizes approved money by ticket. `output/resolved_tickets.json` contains the structured outcomes and a cash reconciliation flag. `output/resolved_board.html` contains actual React screenshots for all three resolved tickets. A live rent continuation also exposed two failures: Facilities attempted Boss-only writes, which were refused, and the agents mistook the automatic monthly due-date advancement for a conflict. Role-specific tool schemas now prevent offering those writes to specialists. `ticket_state.timing.rent_transitions` deterministically compares the paid obligation with the next month, while explicitly separating the shop date from execution timestamps. The original failed attempts and corrected review remain in the audit.

The quote calculator was added after a real run mislabeled a $52 offer as exactly 10% below $58. It returns 10.34% and distinguishes the $176 cost basis of eight existing units from the $264 cash cost of twelve missing units. A real decision-review run corrects the saved business record; the original remains in the audit.

The Reflection tab evaluates the three observed runs and is based on the recorded execution, including corrections.

The isolated MCP tests verify approval authorization and idempotency, financial updates, cash rechecks, vendor blocks, incoming-stock semantics, resolution prerequisites and reset. The React production build checks TypeScript and bundle creation. Browser verification checks the visible board, run initiation, real agent activity, pending approval state and subsequent payment/result rendering. Final recorded results and any remaining limitations are summarized in `output/verification.md`.
