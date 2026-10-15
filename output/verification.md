# Homework 5 Verification

The verified user story is ticket selection in React → FastAPI run initiation → a real PydanticAI team through Portkey → MCP shop reads and writes → real activity and approval state rendered in the browser.

| Boundary | Evidence |
| --- | --- |
| React renders real database state | Browser shows all three tickets, shop date 2026-08-31 and $3,400 starting checking. |
| Browser → API | Reset and ticket-start buttons succeeded through the visible board; agent events refreshed automatically. |
| API → MCP | FastAPI owns a real FastMCP stdio connection; three original smoke calls matched SQLite. |
| Agents → model | gpt-6-luna through Portkey produced actual role reports and tool calls. The first failed tool-calling setting is retained in the audit and was corrected without switching models. |
| MCP → data | Six isolated real-protocol tests pass, including cash, approvals, vendor block, quote math, inventory semantics and reset. |
| Human gate → UI | Both prepared requests were approved after explicit chat authorization. The dashboard recorded $2,400 rent and $840 invoice payments, reducing checking from $3,400 to $1,000 and then $160. No duplicate payments were made. |
| Quote accuracy | The real initial $52 hoodie decision was reviewed after deterministic MCP quote arithmetic caught its inaccurate “10%” label. The corrected record reports 10.34% discount and 57.69% gross margin, with no payment. |
| API mutation guards | Reset without the human-action header returned 403; a foreign browser origin returned 403; unknown ticket returned 404. |
| Production frontend | TypeScript and Vite production build pass. |
| Original database | SHA-256 matches the original database inside the supplied data ZIP; see original_db_integrity.json. |

Current cash/run status is recorded in `resolved_tickets.json`; final screenshot coverage is recorded in `screenshot_manifest.json`. Only actual captures are embedded in `resolved_board.html`. `expected_plans.json` was saved before model execution and remains unchanged in substance. The audit includes earlier setup errors and the original and corrected hoodie decision.

All three operational tickets are resolved. Invoice 501 is paid and the lease next due date is 2026-10-02. The customer drafts remain unsent, no inventory receipt or sale is invented, and checking reconciles to $160. The rent continuation exposed role-permission and business-date interpretation failures; the refused writes remain in the audit, role-specific schemas prevent those specialist writes, and a deterministic timing check supported a real review that corrected the saved outcome. Final screenshots and reflection are included. The student chose to submit to Canvas personally.
