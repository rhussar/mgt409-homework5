# Campus Customs Multi-Agent Operations — Homework 5

Repository: [https://github.com/rhussar/mgt409-homework5](https://github.com/rhussar/mgt409-homework5)

A local shop operations desk with five PydanticAI agents, a FastMCP shop-tools server, a FastAPI backend, and a React + Vite + TypeScript dashboard. Every agent uses **gpt-6-luna through Portkey**. All runtime shop reads and writes go through MCP; SQLite access is confined to the MCP server, documentation generation and isolated verification tests.

## Setup

Use Python 3.12+ and Node.js 20.19+ (or 22.12+). Run these commands from this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `PORTKEY_API_KEY` in `.env`. Do not commit the real file. No OpenAI key is needed. For this local workspace only, the backend also reads an existing parent `.env` if the variable was not set here. The model name is fixed in code; no override selects another model.

The supplied `data/campus_customs.db` is the original. The working file is `data/campus_customs_new.db`. To start completely fresh with servers stopped:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The MCP server adds five small workflow tables to the working copy for approvals, decisions, drafts, exact price quotes and incoming purchase orders. The original is never modified.

## MCP connection and smoke test

The server speaks stdio:

```bash
python mcp_server/server.py
```

A standalone stdio server waits for an MCP client, so it is normal for it not to print a web URL. `.mcp.json` configures compatible clients. Codex uses `.codex/config.toml`; start Codex in this folder after setup so its relative paths resolve here. Private approval and reset tools are disabled in that Codex connection. A trusted project/new client session may be required to load changed MCP configuration. The connection is project-local rather than a change to global servers.

Run the reproducible protocol smoke test:

```bash
python scripts/mcp_smoke.py
```

It starts a subprocess over real MCP stdio, invokes the three original tools and checks returned values against the database. Evidence is written to `output/mcp_smoke.json`. This evidence identifies programmatic MCP calls honestly; it does not pretend that a screenshot or native-tool transcript was captured.

## Start the backend and board

In one terminal, with the virtual environment active:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend starts and manages its **own MCP stdio subprocess** and shares that client with all five agents. You do not need to keep a separate manually launched MCP server running. Backend health is at `http://localhost:8000/health`; API docs are at `http://localhost:8000/docs`.

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. The board calls `http://localhost:8000`; CORS accepts the localhost and 127.0.0.1 Vite origins on port 5173. Both development servers should remain bound to the local machine. This is a single-operator homework app, not a production authentication system.

## Run the three tickets

1. Use **Reset desk** before a full run. This restores the working copy and starts a fresh evidence session. It preserves the complete audit history and Expected plans.
2. Note the starting checking balance. Run each ticket from the board. Fixed obligations deserve priority; the supplied data has $2,400 rent and an $840 vendor invoice competing with purchases for $3,400 cash.
3. When a gold approval card appears, review the amount and projected balance. A human approves or declines. Preparation does not pay; only the human route can execute. The approver name is self-attested for this local simulation.
4. After the decision, click **Continue ticket**. Agents read persisted state, finish the appropriate draft/decision and close the operational task. A closed task does not mean stock arrived or a customer accepted an offer.
5. Review Team summary and Customer draft. Drafts are never sent, no vendor is contacted, and no customer revenue is credited.
6. Use **Export evidence**. The backend also refreshes reports automatically after each run and human decision.

`output/desk_tickets.html` opens directly in a browser and compares the original Expected plan with actual recorded delegations and tools. Its Cash tab reconciles every approved payment to checking. Its Reflection tab evaluates all three recorded ticket runs, including the corrections found during verification. `output/resolved_tickets.json` includes final statuses, outcomes, individual contributions and human decisions. `output/resolved_board.html` holds the final board screenshots when the recorded run is complete.

An error or interruption leaves the real audit trail intact. Continue the unresolved ticket after fixing the cause, or reset for a new full run. No mock agent results replace failed model calls. The working database and evidence files are included for grading; `.venv`, `node_modules`, secrets and local runtime state are excluded.

## Checks

```bash
python -m pytest tests -q
python scripts/mcp_smoke.py
cd frontend
npm run build
```

The financial tests use temporary database copies and real MCP transport, with no model calls. They cover human authorization, duplicate approvals, insufficient cash at preparation and payment time, the vendor block, incoming stock, resolution prerequisites and reset. Live model runs use the same bounded team as the board. See `output/harness.md` for models, tools, routes, safeguards and limits.

## Submission

Review the prompt log, reflection, screenshots and cash reconciliation before publishing. Include both databases, code, `requirements.txt`, `frontend/package-lock.json`, `.env.example`, `.gitignore`, `.mcp.json`, `.codex/config.toml`, and output evidence. Exclude all real credentials and dependency directories. Publishing and Canvas submission are separate final steps; `output/github_url.txt` is populated only after a real public repository exists.

## References

- [PydanticAI multi-agent applications](https://pydantic.dev/docs/ai/guides/multi-agent-applications/)
- [FastMCP client](https://gofastmcp.com/clients/client)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp)
