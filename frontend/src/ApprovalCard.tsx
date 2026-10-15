import {useState} from 'react'
import type {Approval} from './types'
import {money} from './types'
export function ApprovalCard({approval,balance,disabled,onDecide}:{approval:Approval;balance:number;disabled:boolean;onDecide:(id:string,approve:boolean,name:string)=>Promise<void>}){
 const [name,setName]=useState('Ronan')
 const [reviewing,setReviewing]=useState(false)
 return <section className="approval-card" aria-label="Human approval request">
  <div className="eyebrow"><span className="dot amber"/> YOUR DECISION REQUIRED</div>
  <div className="approval-heading"><h3>{approval.kind==='rent'?'Shop rent':approval.kind==='invoice'?'Vendor invoice':'Inventory purchase'}</h3><strong>{money(approval.amount)}</strong></div>
  <p>{approval.description}</p><div className="balance-preview"><span>Checking after approval</span><strong>{money(balance-approval.amount)}</strong></div>
  <p className="fine">This pays from the simulated shop database. The agents have prepared the request and are waiting for you.</p>
  {reviewing?<><label className="name-label">Approved by<input value={name} maxLength={100} onChange={e=>setName(e.target.value)} /></label><div className="button-row"><button className="primary" disabled={disabled||!name.trim()||balance<approval.amount} onClick={()=>void onDecide(approval.id,true,name.trim())}>Confirm payment · {money(approval.amount)}</button><button className="quiet" onClick={()=>setReviewing(false)}>Back</button></div></>:<div className="button-row"><button className="primary" disabled={disabled||balance<approval.amount} onClick={()=>setReviewing(true)}>Review & approve <span>↗</span></button><button className="quiet danger" disabled={disabled} onClick={()=>void onDecide(approval.id,false,name.trim()||'Human')}>Decline</button></div>}
 </section>
}
