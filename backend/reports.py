"""Render evidence from MCP snapshots and real audit events, never invented runs."""
import html
import json
from collections import defaultdict
from pathlib import Path
from audit import OUTPUT, atomic_json

EXPECTED = {
    '101': {
        'first': 'Boss → Inventory: verify the exact size-S tee shortage and its linked invoice.',
        'delegations': ['Inventory → Accounting: check invoice 501 and vendor shipping block; prepare the $840 bill for human approval.', 'Boss → Customer Service after approval: draft an availability update using the vendor lead time. Boss records the decision and closes operational handling with stock still pending.'],
        'tools': ['ticket_state', 'read_ticket', 'check_inventory', 'financial_snapshot', 'prepare_payment', 'save_customer_draft', 'save_decision', 'resolve_ticket'],
        'facts': 'Zero size-S tees. Invoice 501 is $840, due August 28, and blocks Bulldog Print Co. The shop date is August 31; vendor lead time is 5 days. Paying this existing reprint bill does not prove receipt of a tee or justify charging for the same reprint twice.'},
    '102': {
        'first': 'Boss → Facilities: verify the lease, landlord, amount, and due date.',
        'delegations': ['Facilities → Accounting: check cash and prepare the $2,400 rent payment for human approval.', 'Facilities verifies the payment and next lease due date; Boss records the decision and closes the ticket.'],
        'tools': ['ticket_state', 'read_ticket', 'financial_snapshot', 'prepare_payment', 'save_decision', 'resolve_ticket'],
        'facts': 'Chapel Street shop rent is $2,400 due September 2, two days after desk.date_today. Starting cash is $3,400. Rent and invoice 501 together leave $160. Pay the fixed obligations before considering discretionary purchases.'},
    '103': {
        'first': 'Boss → Inventory: establish that 8 medium hoodies cannot fulfill a 20-unit request.',
        'delegations': ['Inventory → Accounting: evaluate the 12-unit shortfall, modeled restock cost, and a sustainable discount.', 'Boss chooses a proposed manager price exception; Customer Service saves a counteroffer that states the stock limit. Boss closes the desk task without claiming a completed sale.'],
        'tools': ['ticket_state', 'check_inventory', 'financial_snapshot', 'save_decision', 'save_customer_draft', 'resolve_ticket'],
        'facts': '8 medium hoodies are available; 12 are missing. At $22 unit cost the shortfall costs $264, exceeding the $160 left after bills by $104. List price is $58. A possible $50 offer would earn $28 unit gross profit and 56% gross margin, but this is a proposed manager exception, not a database policy or an accepted sale.'}
}

def initialize_plan():
    path = OUTPUT / 'expected_plans.json'
    if not path.exists():
        atomic_json(path, {'written_before_agent_runs': True, 'shop_date': '2026-08-31', 'plans': EXPECTED})

def tag(text):
    return html.escape(str(text))

def list_html(items):
    return '<ul>' + ''.join('<li>'+tag(x)+'</li>' for x in items) + '</ul>'

def export(snapshot, events, session_id, starting_cash):
    initialize_plan()
    expected = json.loads((OUTPUT / 'expected_plans.json').read_text())['plans']
    current = [e for e in events if e['session_id'] == session_id]
    contributions = defaultdict(lambda: defaultdict(list))
    for e in current:
        if e['event'] == 'agent_complete':
            contributions[e['ticket_id']][e['agent']].append(e['summary'])
    resolved = []
    panels = []
    cash_rows = []
    spent = 0
    for record in snapshot['tickets']:
        t = record['ticket']; tid = t['id']; plan = expected[str(tid)]
        payment_total = sum(a['amount'] for a in record['approvals'] if a['status'] == 'approved')
        spent += round(payment_total * 100)
        cash_rows.append(f'<tr><td>#{tid}</td><td>${payment_total:,.2f}</td><td>'+tag('; '.join(a['description'] for a in record['approvals'] if a['status']=='approved') or 'No cash payment recorded')+'</td></tr>')
        entry = {'id': tid, 'status': t['status'], 'outcome': record['decisions'][0]['decision'] if record['decisions'] else 'Not yet decided',
            'agent_contributions': dict(contributions[tid]), 'human_approvals': record['approvals'],
            'drafts': record['drafts'], 'quotes': record.get('quotes', []), 'purchase_orders': record['purchase_orders'], 'cash_out': payment_total}
        resolved.append(entry)
        observed = [e for e in current if e['ticket_id']==tid and e['event'] in ('delegation','tool_call')]
        actual = '<p>Not run yet.</p>' if not observed else ('<p><strong>Status: '+tag(t['status'])+'</strong></p><p>'+tag(entry['outcome'])+'</p>' +
            '<h3>Agents and tools observed</h3><ol>'+''.join('<li><strong>'+tag(e['agent'])+'</strong> · '+tag(e['tool'])+' '+tag(json.dumps(e['arguments'],ensure_ascii=False))+'</li>' for e in observed)+'</ol>' +
            '<h3>Agent contributions</h3>'+''.join('<p><strong>'+tag(agent)+'</strong>: '+tag(' '.join(summaries))+'</p>' for agent,summaries in contributions[tid].items())+
            '<h3>Human decisions</h3>'+list_html([f"{a['kind']}: ${a['amount']:,.2f}; {a['status']}; approver: {a['approved_by'] or 'pending'}" for a in record['approvals']])+
            '<h3>Customer draft</h3>'+''.join('<blockquote>'+tag(d['body']).replace('\n','<br>')+'</blockquote>' for d in record['drafts']))
        panels.append(f'<section id="ticket{tid}" class="panel"><p class="eyebrow">TICKET {tid}</p><h1>{tag(t["subject"])}</h1><h2>Expected</h2><p>{tag(plan["first"])}</p>'+list_html(plan['delegations'])+'<p><strong>MCP tools:</strong> '+tag(', '.join(plan['tools']))+'</p><p>'+tag(plan['facts'])+'</p><h2>Actual</h2>'+actual+'</section>')
    balance = next(a['balance'] for a in snapshot['cash_accounts'] if a['name']=='checking')
    expected_balance = round(starting_cash-spent/100,2)
    cash_panel = f'<section id="cash" class="panel"><p class="eyebrow">CASH LEDGER</p><h1>Every dollar accounted for</h1><p>Starting checking: <strong>${starting_cash:,.2f}</strong></p><table><thead><tr><th>Ticket</th><th>Cash out</th><th>Reason</th></tr></thead><tbody>'+''.join(cash_rows)+f'</tbody></table><p>Ending checking in database: <strong>${balance:,.2f}</strong></p><p>Reconciliation: ${starting_cash:,.2f} − ${spent/100:,.2f} = ${expected_balance:,.2f}. '+('Matches.' if expected_balance==balance else 'MISMATCH — investigate before submission.')+'</p><p>No revenue is modeled. Quotes and drafts do not add cash.</p></section>'
    running_cents = round(starting_cash * 100)
    chronological = []
    payment_tickets = {a['payment_id']:r['ticket']['id'] for r in snapshot['tickets'] for a in r['approvals'] if a['status']=='approved'}
    for payment in sorted(snapshot['payments'],key=lambda p:p['id']):
        running_cents -= round(payment['amount']*100)
        chronological.append('<tr><td>'+tag(payment_tickets.get(payment['id'],'—'))+'</td><td>'+tag(payment['kind'])+'</td><td>'+tag(f"${payment['amount']:,.2f}")+'</td><td>'+tag(f"${running_cents/100:,.2f}")+'</td></tr>')
    cash_panel = cash_panel.replace('</section>', '<h2>Approved payment sequence</h2><table><thead><tr><th>Ticket</th><th>Payment</th><th>Cash out</th><th>Checking after payment</th></tr></thead><tbody>'+''.join(chronological)+'</tbody></table></section>')
    complete = all(t['status']=='resolved' for t in resolved)
    reflection = reflection_html(resolved, current) if complete else '<p>The reflection will be drafted after the real ticket runs and human approval decisions.</p>'
    panels += [cash_panel, '<section id="reflection" class="panel"><p class="eyebrow">REFLECTION</p><h1>What the team did well, and where it added work</h1>'+reflection+'</section>']
    buttons=''.join(f'<button role="tab" aria-selected="false" data-panel="ticket{t["id"]}">Ticket {t["id"]}</button>' for t in resolved)+'<button role="tab" aria-selected="false" data-panel="cash">Cash</button><button role="tab" aria-selected="false" data-panel="reflection">Reflection</button>'
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Campus Customs Ticket Evidence</title><style>
    :root{font:16px/1.65 system-ui;color:#172d45;background:#f1f0e9}body{margin:0}header{padding:30px 6%;background:#132c45;color:white}header strong{font:28px Georgia}nav{display:flex;gap:8px;flex-wrap:wrap;padding:22px 6%}button{padding:12px 20px;border:1px solid #b9c3ca;background:white;border-radius:6px;color:#172d45;cursor:pointer}button[aria-selected=true]{background:#172d45;color:white}.panel{display:none;max-width:1000px;margin:0 auto 50px;padding:35px;background:#fff;border:1px solid #d6dad8;border-radius:10px}.panel.active{display:block}h1{font:40px Georgia}h2{border-top:1px solid #ddd;padding-top:22px}.eyebrow{letter-spacing:.15em;font-size:12px;color:#617669}li{margin:10px 0;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{padding:14px;text-align:left;border-bottom:1px solid #ddd}blockquote{border-left:3px solid #c2a76a;margin-left:0;padding-left:20px}@media(max-width:700px){.panel{margin:0 12px;padding:22px}h1{font-size:30px}}
    </style><header><strong>Campus Customs</strong><p>Expected plans, actual runs, and cash evidence</p></header><nav role="tablist">'''+buttons+'</nav>'+''.join(panels)+'''<script>const buttons=document.querySelectorAll('[data-panel]');function select(b){buttons.forEach(x=>x.setAttribute('aria-selected',String(x===b)));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.panel))}buttons.forEach((b,i)=>{b.onclick=()=>select(b);b.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const n=buttons[(i+(e.key==='ArrowRight'?1:buttons.length-1))%buttons.length];select(n);n.focus()}}});select(buttons[0])</script></html>'''
    (OUTPUT / 'desk_tickets.html').write_text(document)
    atomic_json(OUTPUT / 'resolved_tickets.json', {'session_id': session_id, 'complete': complete, 'starting_checking':starting_cash, 'ending_checking':balance,'cash_reconciles':expected_balance==balance,'tickets':resolved})


def reflection_html(tickets, events):
    chunks=[]
    for t in tickets:
        tid=t['id']; agents=list(t['agent_contributions'])
        calls=[e['tool'] for e in events if e['ticket_id']==tid and e['event']=='tool_call']
        delegations=[e for e in events if e['ticket_id']==tid and e['event']=='delegation']
        first = delegations[0]['arguments']['target'] if delegations else 'none'
        planned = {101:'inventory',102:'facilities',103:'inventory'}[tid]
        route = '; '.join(e['agent']+' → '+e['arguments']['target'] for e in delegations)
        comparison = ('The first delegation matched Expected: ' + first + '.') if first == planned else ('Expected first contact was ' + planned + '; Actual first contact was ' + first + '.')
        chunks.append(f'<h2>Ticket {tid}: performance and Expected versus Actual</h2><p>'+tag(t['outcome'])+'</p><p>'+tag(f"Actual participants: {', '.join(agents)}. Recorded {len(delegations)} delegation calls. Tools used: {', '.join(dict.fromkeys(calls))}. Cash out: ${t['cash_out']:,.2f}.")+'</p>')
        chunks.append('<p>'+tag(comparison+' Actual delegation sequence: '+route)+ '</p>')
        if tid==101:
            chunks.append('<p>The plan started with Inventory and followed the vendor invoice to Accounting. Actual took the route listed above. A direct first call to Accounting can address the linked bill sooner than the planned Inventory-first route, although stock and lead time still need verification. Payment approval required a continuation, so repeated reads after approval serve a verification purpose. The key success is clearing the shipping block without pretending the zero-stock tee is now in hand. A five-day lead time is only an estimate from the shop date. Paying an invoice is not a stock receipt, and the draft must preserve that distinction.</p>')
        elif tid==102:
            chunks.append('<p>The plan used Facilities for the lease and Accounting for payment preparation. Actual included the planned Facilities → Accounting chain, then additional direct Boss → Accounting consultations before payment preparation. That repetition added model calls. Boss also tried to prepare payment directly and the role guard refused it, after which Accounting prepared the request. The payment control worked, but the routing was less efficient than Expected. Rent is evaluated against August 31, not the computer clock. The payment record and advanced lease due date are stronger evidence than an agent saying “done.” Human approval is the essential control.</p><p>A continuation failed when Facilities attempted Boss-only decision writes. The server refused them, and role-specific tool schemas were then added before resuming. A later report also confused the September 2 obligation just paid with the October 2 next due date, mixing the business schedule with wall-clock audit timestamps. A deterministic rent-transition check and a real review run corrected that explanation. The final lease date is October 2, consistent with advancing the paid September obligation by one calendar month. These repairs make the final state reliable, but the extra handoffs and review work make this ticket a clear case where one agent with a payment approval gate would have been simpler.</p>')
        else:
            chunks.append('<p>The plan called for Inventory, Accounting and a Customer Service draft, with Boss deciding the exception. Actual used the relevant specialists directly from Boss, whereas Expected anticipated Inventory consulting Accounting. The roles were appropriate, but the delegation topology differed. The saved quote below gives the actual price and arithmetic; the $50 in Expected was only an illustrative alternative. Stock and affordability are separate: eight medium hoodies are available, but twelve additional units cost $264, more than the $160 remaining after rent and the invoice. A counteroffer can resolve the desk decision without fulfilling twenty units. No draft or quoted margin should be counted as revenue or customer acceptance.</p>')
        if t.get('quotes'):
            q=t['quotes'][0]
            chunks.append('<p>'+tag(f"Verified offer: {q['quantity']} units × ${q['unit_price']:.2f} = ${q['total_if_accepted']:.2f} if accepted. Discount {q['discount_percent']:.2f}%; gross profit ${q['unit_gross_profit']:.2f}/unit and ${q['total_gross_profit']:.2f} total; gross margin {q['gross_margin_percent']:.2f}%. The ${q['existing_stock_cost_basis']:.2f} cost basis is already-held inventory, not a new payment. New purchase cost for the full shortfall would be ${q['modeled_full_shortfall_purchase_cost']:.2f}.")+'</p><p>The initial model decision incorrectly called $52 exactly 10% off $58 and blurred existing inventory cost with new spending. A deterministic MCP quote tool and a separate real review run corrected those claims. Keeping both versions in the audit makes this a measured correction rather than an unexplained edit. This is also a limit of relying on language-model arithmetic without tool checks.</p>')
    chunks.append('<h2>Where one agent with tools would be simpler</h2><p>Rent is essentially a lease lookup, cash check, approval request and transactional update. One agent with those tools could do it with fewer handoffs while retaining the exact same human payment gate. The tee request also needs only a stock check, a linked-invoice check and a draft; separating those into roles makes responsibilities visible, but repeats context and reads. The hoodie case benefits more from distinct stock and financial reviews, although one well-instructed agent could still compute both. Specialist names do not provide safety by themselves: amount validation, cash checks and route isolation do.</p>')
    chunks.append('<h2>Three new problems these tools can address</h2><ol><li>A customer asks for a currently stocked large navy hoodie: Inventory can check SKU and size, Accounting can check the listed price, and Customer Service can draft an accurate availability response. The existing tools support the desk response, not a completed sale.</li><li>A landlord asks whether a recorded rent obligation was paid: Facilities can inspect the lease and Accounting can verify payment history, with Boss recording a documented answer.</li><li>A club requests a different quantity or discount on a stocked product: Inventory can establish capacity, Accounting can compute cost and gross margin, and Boss can approve a proposed price exception for a draft. A new ticket would currently need to be inserted by a manager because this app has no intake tool.</li></ol>')
    chunks.append('<h2>Three problems needing more tools or agents</h2><ol><li>A customer wants to pay for the hoodie offer. Add checkout, payment collection, sales invoices and inventory reservation/fulfillment tools, plus a sales or fulfillment role. This simulation deliberately models no incoming revenue.</li><li>A supplier claims a shipment was delivered, but goods are missing. Add purchase-order line items, supplier confirmations, shipment tracking and receiving/count tools, with a receiving or logistics role. Paying a reprint bill cannot establish what physically arrived.</li><li>A customer asks for a damaged-item refund. Add order lookup, return authorization, refund execution and stock-condition records, with a returns role and a separate human refund approval path. Current customer drafts and generic bill payments are insufficient.</li></ol><h2>Limits of this evaluation</h2><p>These are three tickets in a small fixed database, not a broad accuracy benchmark. The evidence tests routing, state transitions and cash control. It does not test actual supplier service, delivery, customer satisfaction, revenue or demand forecasting. This reflection is based on the recorded execution, including failed attempts and subsequent reviews.</p>')
    return ''.join(chunks)
