"""Financial invariants exercised across real MCP stdio against isolated DB copies."""
import asyncio
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]
TEST_TOKEN = 'isolated-test-authorization'

async def scenario(tmp_path, body):
    path = tmp_path / 'working.db'
    shutil.copyfile(ROOT/'data/campus_customs.db',path)
    original_hash=hashlib.sha256((ROOT/'data/campus_customs.db').read_bytes()).hexdigest()
    transport=StdioTransport(command=sys.executable,args=[str(ROOT/'mcp_server/server.py')],env={'CAMPUS_DB_PATH':str(path),'HUMAN_APPROVAL_TOKEN':TEST_TOKEN})
    async with Client(transport) as client:
        async def call(name, **arguments):
            return (await client.call_tool(name,arguments)).data
        await body(call, path)
    assert hashlib.sha256((ROOT/'data/campus_customs.db').read_bytes()).hexdigest()==original_hash

async def approve(call, request):
    return await call('decide_approval',request_id=request['request']['id'],approve=True,approved_by='Test human',authorization=TEST_TOKEN)

def test_payment_requires_human_and_is_idempotent(tmp_path):
    async def body(call,path):
        req=await call('prepare_payment',ticket_id=101,kind='invoice',ref_id=501,reason='Clear reprint invoice')
        assert req['request']['amount']==840
        assert (await call('financial_snapshot'))['cash_accounts'][0]['balance']==3400
        with pytest.raises(Exception, match='authorization required'):
            await call('decide_approval',request_id=req['request']['id'],approve=True,approved_by='Agent',authorization='wrong')
        first=await approve(call,req)
        second=await approve(call,req)
        assert first['balance']==2560
        assert second['idempotent'] is True
        snap=await call('financial_snapshot')
        assert snap['invoices'][0]['status']=='paid'
        assert len(snap['payments'])==1
        assert snap['cash_accounts'][0]['balance']==2560
    asyncio.run(scenario(tmp_path,body))

def test_rent_and_cash_shortfall(tmp_path):
    async def body(call,path):
        bill=await call('prepare_payment',ticket_id=101,kind='invoice',ref_id=501,reason='Invoice')
        await approve(call,bill)
        rent=await call('prepare_payment',ticket_id=102,kind='rent',ref_id=1,reason='Rent')
        assert (await approve(call,rent))['balance']==160
        assert (await call('financial_snapshot'))['leases'][0]['next_due']=='2026-10-02'
        timing=(await call('ticket_state',ticket_id=102))['timing']
        assert timing['business_today']=='2026-08-31'
        assert timing['rent_transitions'][0]['transition_matches'] is True
        assert timing['rent_transitions'][0]['paid_obligation_due']=='2026-09-02'
        purchase=await call('prepare_purchase',ticket_id=103,quantity=12,vendor_id=1,reason='Twelve missing hoodies')
        assert purchase['ok'] is False
        assert purchase['requested']==264
        assert (await call('financial_snapshot'))['cash_accounts'][0]['balance']==160
    asyncio.run(scenario(tmp_path,body))

def test_vendor_block_and_incoming_stock(tmp_path):
    async def body(call,path):
        blocked=await call('prepare_purchase',ticket_id=103,quantity=12,vendor_id=1,reason='Restock')
        assert blocked['ok'] is False and 'Vendor blocked' in blocked['error']
        await approve(call,await call('prepare_payment',ticket_id=101,kind='invoice',ref_id=501,reason='Invoice'))
        purchase=await call('prepare_purchase',ticket_id=103,quantity=12,vendor_id=1,reason='Restock')
        assert purchase['request']['amount']==264
        await approve(call,purchase)
        state=await call('ticket_state',ticket_id=103)
        assert state['purchase_orders'][0]['estimated_arrival']=='2026-09-05'
        assert state['purchase_orders'][0]['status']=='ordered_not_received'
        assert (await call('check_inventory',sku='CC-HOOD-NAVY',size='M'))['inventory']['qty']==8
    asyncio.run(scenario(tmp_path,body))

def test_cash_rechecked_at_approval_and_pending_reserved(tmp_path):
    async def body(call,path):
        req=await call('prepare_payment',ticket_id=102,kind='rent',ref_id=1,reason='Rent')
        bill=await call('prepare_payment',ticket_id=101,kind='invoice',ref_id=501,reason='Invoice')
        assert bill['ok'] is True
        # Simulate an intervening manager adjustment; the payment tool must recheck.
        with sqlite3.connect(path) as db:
            db.execute("UPDATE cash_accounts SET balance=100 WHERE name='checking'")
        result=await approve(call,req)
        assert result['ok'] is False
        assert (await call('financial_snapshot'))['cash_accounts'][0]['balance']==100
        assert not (await call('financial_snapshot'))['payments']
    asyncio.run(scenario(tmp_path,body))

def test_resolution_checks_and_reset(tmp_path):
    async def body(call,path):
        req=await call('prepare_payment',ticket_id=101,kind='invoice',ref_id=501,reason='Invoice')
        premature=await call('resolve_ticket',ticket_id=101,outcome='Done')
        assert premature['ok'] is False
        await approve(call,req)
        await call('save_decision',ticket_id=101,decision='Invoice cleared, fulfillment deferred until stock arrives.')
        assert (await call('resolve_ticket',ticket_id=101,outcome='Done'))['ok'] is False
        await call('save_customer_draft',ticket_id=101,subject='Tee availability',body='The small tee is out of stock. Restock timing is provisional.')
        assert (await call('resolve_ticket',ticket_id=101,outcome='Invoice cleared; draft ready, physical fulfillment pending.'))['ok'] is True
        await call('reset_shop',authorization=TEST_TOKEN)
        snap=await call('list_tickets')
        assert snap['cash_accounts'][0]['balance']==3400
        assert all(r['ticket']['status']=='open' for r in snap['tickets'])
        assert not snap['payments']
    asyncio.run(scenario(tmp_path,body))

def test_quote_math_does_not_spend_existing_stock_cost(tmp_path):
    async def body(call,path):
        q=await call('quote_offer',ticket_id=103,quantity=8,unit_price=52)
        assert q['discount_percent']==10.34
        assert q['gross_margin_percent']==57.69
        assert q['total_if_accepted']==416
        assert q['existing_stock_cost_basis']==176
        assert q['total_gross_profit']==240
        assert q['modeled_full_shortfall_purchase_cost']==264
        assert q['cash_change_now']==0
        assert (await call('financial_snapshot'))['cash_accounts'][0]['balance']==3400
        with pytest.raises(Exception,match='exact-size stock'):
            await call('quote_offer',ticket_id=103,quantity=20,unit_price=52)
    asyncio.run(scenario(tmp_path,body))
