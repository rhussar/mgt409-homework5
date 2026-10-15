"""Local FastAPI dashboard API. Run: uvicorn main:app --reload --port 8000."""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from agents import Team, MODEL
from audit import Auditor, OUTPUT, atomic_json
from models import ApprovalDecision, ResetRequest
from reports import export, initialize_plan
from shop import Shop

shop = Shop()
auditor = Auditor()
runtime_path = OUTPUT / 'session.json'
legacy_path = OUTPUT / 'runtime.json'
if not runtime_path.exists() and legacy_path.exists():
    atomic_json(runtime_path, json.loads(legacy_path.read_text()))
runtime = json.loads(runtime_path.read_text()) if runtime_path.exists() else {'session_id': str(uuid.uuid4()), 'starting_cash': None, 'runs': {}}
for run in runtime['runs'].values():
    if run['status'] == 'running':
        run['status'] = 'interrupted'
        run['error'] = 'Backend restarted during the run; use Continue ticket.'
active_task = None
active_ticket = None


def save_runtime():
    atomic_json(runtime_path, runtime)

async def snapshot():
    return await shop.call('list_tickets')

async def write_reports():
    data = await snapshot()
    if runtime['starting_cash'] is None:
        runtime['starting_cash'] = next(a['balance'] for a in data['cash_accounts'] if a['name']=='checking')
        save_runtime()
    export(data, auditor.events, runtime['session_id'], runtime['starting_cash'])

@asynccontextmanager
async def lifespan(app):
    initialize_plan()
    async with shop.client:
        await write_reports()
        yield
        if active_task and not active_task.done():
            active_task.cancel()
            try:
                await active_task
            except asyncio.CancelledError:
                pass

app = FastAPI(title='Campus Customs Operations', lifespan=lifespan)
ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173']
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=['GET','POST'], allow_headers=['Content-Type','X-Desk-Action'])

@app.middleware('http')
async def local_mutations(request: Request, call_next):
    if request.method == 'POST':
        if request.headers.get('origin') not in (None, *ORIGINS) or request.headers.get('x-desk-action') != 'human':
            return JSONResponse(status_code=403, content={'detail':'Use the local human dashboard for actions.'})
    return await call_next(request)

@app.get('/health')
async def health():
    return {'ok': True, 'model': MODEL, 'mcp': 'connected'}

@app.get('/api/desk')
async def desk():
    data = await snapshot()
    return {**data, 'runs': runtime['runs'], 'session_id': runtime['session_id'], 'starting_cash':runtime['starting_cash'], 'active_ticket': active_ticket}

@app.get('/api/tickets')
async def tickets():
    return (await snapshot())['tickets']

@app.get('/api/cash')
async def cash():
    data = await shop.call('financial_snapshot')
    return {'accounts':data['cash_accounts'], 'payments':data['payments']}

@app.get('/api/events')
async def events(after: int=0, ticket_id: int | None=None):
    return [e for e in auditor.events if e['session_id']==runtime['session_id'] and e['id']>after and (ticket_id is None or e['ticket_id']==ticket_id)]

async def execute(ticket_id, run_id, review=False):
    global active_ticket
    team = Team(shop, auditor, runtime['session_id'], run_id, ticket_id)
    try:
        auditor.append(session_id=runtime['session_id'],run_id=run_id,ticket_id=ticket_id,agent='system',event='run_start',summary='Human started or continued the ticket team.')
        report = await team.run(review=review)
        state = await shop.call('ticket_state', {'ticket_id':ticket_id})
        waiting = any(r['status']=='pending' for r in state['approvals'])
        status = 'resolved' if state['ticket']['status']=='resolved' else ('waiting_for_approval' if waiting else 'blocked')
        runtime['runs'][str(ticket_id)].update(status=status, report=report)
        auditor.append(session_id=runtime['session_id'],run_id=run_id,ticket_id=ticket_id,agent='system',event='run_complete',summary=report['summary'],stop_reason=status)
    except Exception as error:
        # Do not print request headers, credentials, or full provider payloads.
        message = f'{type(error).__name__}: {str(error)[:400]}'
        runtime['runs'][str(ticket_id)].update(status='error',error=message)
        auditor.append(session_id=runtime['session_id'],run_id=run_id,ticket_id=ticket_id,agent='system',event='run_error',summary=message,stop_reason='error')
    finally:
        active_ticket = None
        save_runtime()
        await write_reports()

async def start(ticket_id, review=False):
    global active_task, active_ticket
    if active_task and not active_task.done():
        raise HTTPException(409,'A ticket team is already running. Wait for it to finish.')
    try:
        state = await shop.call('ticket_state', {'ticket_id':ticket_id})
    except Exception:
        raise HTTPException(404,'Unknown ticket')
    if state['ticket']['status']=='resolved' and not review:
        raise HTTPException(409,'Ticket already resolved')
    if any(r['status']=='pending' for r in state['approvals']):
        raise HTTPException(409,'Review the pending approval before continuing')
    run_id=str(uuid.uuid4())
    runtime['runs'][str(ticket_id)]={'run_id':run_id,'status':'running'}
    active_ticket=ticket_id
    save_runtime()
    active_task=asyncio.create_task(execute(ticket_id,run_id,review=review))
    return {'run_id':run_id,'status':'running'}

@app.post('/api/tickets/{ticket_id}/run', status_code=202)
async def run_ticket(ticket_id: int):
    return await start(ticket_id)

@app.post('/api/tickets/{ticket_id}/review', status_code=202)
async def review_ticket(ticket_id: int):
    return await start(ticket_id, review=True)

@app.post('/api/approvals/{request_id}/decide')
async def decide(request_id: str, decision: ApprovalDecision):
    if active_task and not active_task.done():
        raise HTTPException(409,'Wait for the agents to pause before deciding')
    result=await shop.decide(request_id, decision.approve, decision.approved_by)
    if not result.get('ok'):
        raise HTTPException(409,result.get('error','Payment refused'))
    auditor.append(session_id=runtime['session_id'], ticket_id=result.get('ticket_id'), agent='human',event='approval_decision',
        summary=f'{decision.approved_by} '+('approved' if decision.approve else 'rejected')+' the prepared request.',
        arguments={'request_id':request_id,'approve':decision.approve},result=result)
    await write_reports()
    # Continue is an explicit dashboard action so the human can review the payment result first.
    return result

@app.post('/api/reset')
async def reset(body: ResetRequest):
    if active_task and not active_task.done():
        raise HTTPException(409,'Cannot reset during an active run')
    result=await shop.reset()
    runtime.update(session_id=str(uuid.uuid4()),starting_cash=None,runs={})
    save_runtime()
    auditor.append(session_id=runtime['session_id'],agent='human',event='reset',summary='Human reset the working database before a fresh run.')
    await write_reports()
    return result

@app.post('/api/export')
async def export_evidence():
    if active_task and not active_task.done():
        raise HTTPException(409,'Wait for the run to finish')
    await write_reports()
    return {'ok':True,'output':'output/desk_tickets.html and output/resolved_tickets.json'}
