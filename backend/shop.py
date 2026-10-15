"""One MCP client shared by the backend and agents. No direct shop SQLite access."""
import json
import os
import secrets
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]
AGENT_TOOLS = ('read_ticket', 'ticket_state', 'check_inventory', 'financial_snapshot',
    'quote_offer', 'prepare_payment', 'prepare_purchase', 'save_decision', 'save_customer_draft', 'resolve_ticket')

class Shop:
    def __init__(self):
        self.authorization = secrets.token_urlsafe(32)
        self.client = Client(StdioTransport(command=sys.executable,
            args=[str(ROOT / 'mcp_server/server.py')], cwd=str(ROOT),
            env={'HUMAN_APPROVAL_TOKEN': self.authorization, **({'CAMPUS_DB_PATH': os.environ['CAMPUS_DB_PATH']} if os.getenv('CAMPUS_DB_PATH') else {})}))

    async def call(self, name, arguments=None):
        result = await self.client.call_tool(name, arguments or {})
        if result.data is not None:
            return result.data
        return json.loads(''.join(c.text for c in result.content if hasattr(c, 'text')))

    async def decide(self, request_id, approve, approved_by):
        return await self.call('decide_approval', {'request_id': request_id, 'approve': approve,
            'approved_by': approved_by, 'authorization': self.authorization})

    async def reset(self):
        return await self.call('reset_shop', {'authorization': self.authorization})
