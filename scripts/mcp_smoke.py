"""Exercise the three initial tools over real MCP stdio, then compare with SQLite."""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]

async def main():
    tests = [
        ("Show ticket 101, the shop date, and its linked invoice.", "read_ticket", {"ticket_id": 101}),
        ("Check stock and pricing for the medium navy hoodies requested in ticket 103.", "check_inventory", {"sku": "CC-HOOD-NAVY", "size": "M"}),
        ("Show the checking cash and lease details needed for ticket 102.", "financial_snapshot", {}),
    ]
    evidence = []
    async with Client(StdioTransport(command=sys.executable, args=[str(ROOT / "mcp_server/server.py")])) as client:
        names = {t.name for t in await client.list_tools()}
        with sqlite3.connect(f"file:{ROOT / 'data/campus_customs_new.db'}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            for prompt, tool, arguments in tests:
                assert tool in names
                result = (await client.call_tool(tool, arguments)).data
                if tool == "read_ticket":
                    assert result["ticket"] == dict(db.execute("SELECT * FROM tickets WHERE id=101").fetchone())
                elif tool == "check_inventory":
                    assert result["inventory"] == dict(db.execute("SELECT * FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'").fetchone())
                else:
                    assert result["cash_accounts"] == [dict(r) for r in db.execute("SELECT * FROM cash_accounts")]
                    assert result["leases"] == [dict(r) for r in db.execute("SELECT * FROM leases")]
                evidence.append({"prompt": prompt, "prompt_source": "MCP smoke-test requests executed by Codex", "transport": "MCP stdio via FastMCP Client", "tool": tool, "arguments": arguments, "output": result, "database_match": True})
    (ROOT / "output/mcp_smoke.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence)} real MCP calls matched the database")

if __name__ == "__main__":
    asyncio.run(main())
