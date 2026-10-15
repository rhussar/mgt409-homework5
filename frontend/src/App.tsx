import {useEffect,useRef,useState} from 'react'
import {api} from './api'
import {ApprovalCard} from './ApprovalCard'
import {initials,labels,money,roles} from './types'
import type {Desk,Event,Role} from './types'

function displayStatus(status:string){return status.replaceAll('_',' ')}
function Avatar({role}:{role:string}){return <span className={'avatar role-'+role}>{initials[role]||'CC'}</span>}
function publicEvents(events:Event[]){return events.filter(e=>['agent_start','delegation','tool_call','tool_result','tool_error','agent_complete','approval_decision','run_error','run_complete'].includes(e.event))}
function EventRow({event}:{event:Event}){
 const [expanded,setExpanded]=useState(false)
 const actionable=event.event==='tool_call'||event.event==='tool_result'
 const subtitle=event.event==='delegation'?'delegated to '+labels[(event.arguments as {target:string}).target]:event.event==='agent_start'?'joined the ticket':event.event==='tool_call'?'used '+event.tool:event.event==='tool_result'?'returned from '+event.tool:event.event==='agent_complete'?'finished their work':displayStatus(event.event)
 return <article className={'event-row role-'+event.agent}><Avatar role={event.agent}/><div className="event-body"><header><strong>{labels[event.agent]||event.agent}</strong><span>{subtitle}</span><time>{new Date(event.timestamp).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time></header>{actionable?<><button className="event-toggle" onClick={()=>setExpanded(!expanded)} aria-expanded={expanded}>{event.event==='tool_call'?'View tool arguments':'View database result'} <span>{expanded?'−':'+'}</span></button>{expanded?<pre>{JSON.stringify(event.event==='tool_call'?event.arguments:event.result,null,2)}</pre>:null}</>:<p>{event.summary}</p>}</div></article>
}

export default function App(){
 const [desk,setDesk]=useState<Desk|null>(null),[events,setEvents]=useState<Event[]>([]),[selected,setSelected]=useState(102),[tab,setTab]=useState<'activity'|'decision'|'draft'>('activity')
 const [error,setError]=useState(''),[busy,setBusy]=useState(false),[resetOpen,setResetOpen]=useState(false),[notice,setNotice]=useState('')
 const after=useRef(0),session=useRef('')
 const refresh=useRef<()=>Promise<void>>(async()=>{})
 useEffect(()=>{
  let alive=true,timeout:ReturnType<typeof setTimeout>
  async function update(){
   try{
    const d=await api.desk()
    const changed=session.current!==d.session_id
    const next=await api.events(changed?0:after.current)
    if(!alive)return
    setDesk(d)
    if(changed){session.current=d.session_id;setEvents(next);after.current=next.at(-1)?.id||0}
    else if(next.length){after.current=next[next.length-1].id;setEvents(old=>[...old,...next])}
    setError('')
   }catch(e){if(alive)setError((e as Error).message==='Failed to fetch'?'Cannot reach the desk. Start the backend on localhost:8000.':(e as Error).message)}
  }
  refresh.current=update
  async function poll(){await update();if(alive)timeout=setTimeout(poll,1500)}
  void poll()
  return()=>{alive=false;clearTimeout(timeout)}
 },[])
 async function action(work:()=>Promise<unknown>,message?:string){setBusy(true);setError('');try{await work();await refresh.current();if(message)setNotice(message)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const record=desk?.tickets.find(r=>r.ticket.id===selected),ticket=record?.ticket,run=desk?.runs[String(selected)]
 const cash=desk?.cash_accounts.find(a=>a.name==='checking')?.balance??0
 const complete=desk?.tickets.filter(r=>r.ticket.status==='resolved').length??0
 const ticketEvents=events.filter(e=>e.ticket_id===selected)
 const stream=publicEvents(ticketEvents)
 const pending=record?.approvals.filter(a=>a.status==='pending')??[]
 const running=desk?.active_ticket!=null
 const status=ticket?.status==='resolved'?'resolved':run?.status||'open'
 const roleReportEvents=Object.fromEntries(roles.map(role=>[role,ticketEvents.filter(e=>e.agent===role&&e.event==='agent_complete').at(-1)]))
 const roleSummaries=Object.fromEntries(roles.map(role=>[role,roleReportEvents[role]?.summary]))
 const activeRole=ticketEvents.filter(e=>e.event==='agent_start'||e.event==='tool_call').at(-1)?.agent
 return <div className="app-shell">
  <aside className="sidebar"><a className="wordmark" href="#" aria-label="Campus Customs home"><span className="brand-seal">CC<span>NEW HAVEN</span></span><span>Campus<br/>Customs<small>OPERATIONS DESK</small></span></a><div className="sidebar-divider"/><p className="side-label">WORKSPACE</p><div className="side-active"><span>▦</span> Ticket desk <span className="side-count">03</span></div><div className="sidebar-note"><span className="tiny-label">THE SHOP CLOCK</span><strong>{desk?.desk.date_today||'Connecting…'}</strong><span>Decisions follow the date<br/>on the shop's desk.</span></div><div className="sidebar-bottom"><div className="live-label"><span className={'dot '+(desk?'green':'amber')}/>{desk?'DESK CONNECTED':'CONNECTING'}</div><p>Five roles.<br/>One shared shop.</p><small>Campus Customs · Yale merchandise</small></div></aside>
  <main><header className="topbar"><div><span className="breadcrumb">WORKSPACE</span><span className="slash">/</span><strong>Ticket desk</strong></div><div className="operator"><span>HUMAN IN THE LOOP</span><b>R</b></div></header>
  <div className="main-content"><div className="page-heading"><div><p className="eyebrow">CAMPUS CUSTOMS / DAILY OPERATIONS</p><h1>A good day at the desk.</h1><p className="subtitle">Your team handles the details. You make the calls.</p></div><div className="header-actions"><button className="outline" disabled={busy||running} onClick={()=>void action(api.export,'Evidence files updated in output/.')}>Export evidence <span>↗</span></button><button className="text-button" disabled={busy||running} onClick={()=>setResetOpen(true)}>Reset desk</button></div></div>
  {error?<div role="alert" className="alert error">{error}<button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>:null}
  {notice?<div role="status" className="alert notice">{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss notification">×</button></div>:null}
  <section className="metrics" aria-label="Shop overview"><div className="metric"><span className="metric-label">CHECKING BALANCE <span>↗</span></span><strong>{money(cash)}</strong><small>Cash only moves after your approval</small></div><div className="metric"><span className="metric-label">TICKETS RESOLVED <span>✓</span></span><strong>{complete}<em>/ 3</em></strong><small>{3-complete} {3-complete===1?'ticket needs':'tickets need'} attention</small></div><div className="metric team-metric"><span className="metric-label">YOUR AGENT TEAM</span><div className="avatar-stack">{roles.map(r=><Avatar key={r} role={r}/>)}</div><small>{running?'Team is working on #'+desk?.active_ticket:'Five specialists, ready when you are'}</small></div></section>
  <div className="desk-layout"><section className="ticket-list" aria-label="Tickets"><div className="section-heading"><h2>The ticket board</h2><span>03</span></div><p className="section-caption">Pick a ticket. Put the team to work.</p><div className="ticket-cards">{desk?.tickets.map(({ticket:t,approvals})=>{const s=t.status==='resolved'?'resolved':desk.runs[String(t.id)]?.status||'open';return <button key={t.id} className={'ticket-card '+(selected===t.id?'selected':'')} onClick={()=>{setSelected(t.id);setTab('activity')}} aria-pressed={selected===t.id}><div className="ticket-card-top"><span className="ticket-number">#{t.id}</span><span className={'status '+s}>{s==='waiting_for_approval'?'Approval needed':displayStatus(s)}</span></div><span className="ticket-icon">{t.type==='rent_notice'?'⌂':t.type==='price_override'?'%':'↳'}</span><h3>{t.subject}</h3><p>{t.requester}</p><div className="ticket-card-bottom"><span>{t.type==='rent_notice'?'Facilities & finance':t.type==='price_override'?'Inventory & pricing':'Customer order'}</span><span>{approvals.some(a=>a.status==='pending')?'●':'↗'}</span></div></button>})}</div><div className="desk-rule"><span>✳</span><p><strong>A little oversight goes a long way.</strong>Agents can prepare a payment. Only you can approve it.</p></div></section>
  <section className="work-panel" aria-label="Selected ticket"><div className="work-header"><div><div className="eyebrow">TICKET #{selected} <span className={'status '+status}>{displayStatus(status)}</span></div><h2>{ticket?.subject||'Opening the desk…'}</h2><p>{ticket?.requester}{ticket?.qty?' · '+ticket.qty+' requested · Size '+ticket.size:''}</p></div><button className="primary run-button" disabled={!desk||busy||running||ticket?.status==='resolved'||pending.length>0} onClick={()=>void action(()=>api.run(selected))}>{ticket?.status==='resolved'?'✓ Resolved':running&&desk?.active_ticket===selected?'Team is working…':run?'Continue ticket':'Start team'}<span>{ticket?.status==='resolved'?'':'→'}</span></button></div>
  <div className="ticket-brief"><span>THE REQUEST</span><p>{ticket?.notes.split('\nResolution:')[0]||'Connecting to the shop database.'}</p></div>
  <div className="agent-strip" aria-label="Agent status">{roles.map(r=><div key={r} className={running&&activeRole===r?'is-active':''}><Avatar role={r}/><span>{labels[r]}</span><i className={roleSummaries[r]?'done':''}/></div>)}</div>
  {pending.map(approval=><ApprovalCard key={approval.id} approval={approval} balance={cash} disabled={busy||running} onDecide={async(id,approve,name)=>{await action(()=>api.decide(id,approve,name),approve?'Payment recorded. Continue the ticket to let the team finish.':'Request declined.')}}/>)}
  {record?.approvals.filter(a=>a.status!=='pending').map(a=><div key={a.id} className="payment-receipt"><span>{a.status==='approved'?'✓':'×'} {money(a.amount)} {a.kind} {a.status}</span><small>{a.approved_by}</small></div>)}
  {run?.error?<div className="alert error">{run.error}</div>:null}
  {ticket?.status==='resolved'?<div className="review-row"><button className="text-button" disabled={busy||running} onClick={()=>void action(()=>api.review(selected),'Decision review started. The audit keeps the original and reviewed work.')}>Review decision accuracy ↗</button></div>:null}
  <div className="work-tabs" role="tablist" aria-label="Ticket details">{(['activity','decision','draft'] as const).map(t=><button key={t} role="tab" aria-selected={tab===t} onClick={()=>setTab(t)}>{t==='activity'?'Live activity':t==='decision'?'Team summary':'Customer draft'}{t==='activity'&&stream.length?<span>{stream.length}</span>:null}</button>)}</div>
  <div className="work-body" role="tabpanel">{tab==='activity'?<>{stream.length?<div className="event-stream">{stream.map(e=><EventRow key={e.id} event={e}/>)}</div>:<div className="empty-state"><div className="orbit-mark"><span>CC</span><i/><i/></div><p className="eyebrow">THE TEAM IS READY</p><h3>One ticket. The right people.</h3><p>Start the team to see Boss bring in the specialists<br className="desktop-break"/> this request needs.</p><span className="empty-footnote">Every tool call leaves a trace.</span></div>}{running&&desk?.active_ticket===selected?<div className="working"><span className="dot green"/> Agents are working. Activity updates automatically.</div>:null}</>:tab==='decision'?<div className="summary-content">{record?.decisions.length?record.decisions.map((d,i)=><div key={i} className="decision-note"><span className="eyebrow">BOSS'S DECISION</span><p>{d.decision}</p></div>):<p className="muted">The decision will appear after Boss evaluates the ticket.</p>}{roles.filter(r=>roleSummaries[r]).map((r:Role)=><article className="agent-summary" key={r}><Avatar role={r}/><div><h3>{labels[r]}</h3>{roleReportEvents[r]?.run_id!==run?.run_id?<span className="previous-report">Earlier assessment · refer to the final decision above</span>:null}<p>{roleSummaries[r]}</p></div></article>)}{run?.report?<div className="next-steps"><h3>What remains</h3><ul>{run.report.recommendations.map((r,i)=><li key={i}>{r}</li>)}</ul></div>:null}</div>:<div className="draft-content">{record?.drafts.length?record.drafts.map((d,i)=><article key={i}><span className="draft-stamp">DRAFT · NOT SENT</span><dl><dt>To</dt><dd>{d.recipient}</dd><dt>Subject</dt><dd>{d.subject}</dd></dl><p>{d.body}</p></article>):<div className="empty-message"><h3>No customer draft yet</h3><p>Customer Service drafts appear here when this ticket needs one.</p></div>}</div>}</div>
  </section></div><footer className="page-footer"><span>CC / OPERATIONS DESK</span><p>Facts from the shop. Decisions by people.</p><span>NEW HAVEN, CT</span></footer></div></main>
  {resetOpen?<div className="modal-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="reset-title" className="modal"><p className="eyebrow">FRESH START</p><h2 id="reset-title">Reset the working desk?</h2><p>This restores the original tickets, cash, invoices and stock. The audit history and Expected plans stay saved. Capture any evidence you need first.</p><div className="button-row"><button autoFocus className="outline" onClick={()=>setResetOpen(false)}>Keep working</button><button className="primary" disabled={busy} onClick={()=>void action(async()=>{await api.reset();setResetOpen(false);setTab('activity')},'Desk reset to the original database.')}>Reset working database</button></div></section></div>:null}
 </div>
}
