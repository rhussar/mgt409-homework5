export type Role = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type Approval = { id:string; ticket_id:number; kind:string; amount:number; status:string; description:string; approved_by:string|null; details:string }
export type Ticket = { id:number; type:string; requester:string; subject:string; sku:string|null; size:string|null; qty:number|null; status:string; notes:string }
export type Record = { ticket:Ticket; approvals:Approval[]; drafts:{recipient:string; subject:string; body:string}[]; decisions:{decision:string}[]; purchase_orders:unknown[] }
export type Report = {summary:string;status:string;evidence:string[];recommendations:string[]}
export type Run = {status:string;run_id:string;report?:Report;error?:string}
export type Desk = {desk:{date_today:string};tickets:Record[];cash_accounts:{name:string;balance:number}[];starting_cash:number;active_ticket:number|null;runs:{[id:string]:Run};session_id:string}
export type Event = {id:number;run_id:string|null;timestamp:string;ticket_id:number|null;agent:string;event:string;summary:string;tool:string|null;arguments:unknown;result:unknown;stop_reason:string|null}
export const roles:Role[]=['boss','inventory','accounting','facilities','customer_service']
export const labels:{[key:string]:string}={boss:'Boss',inventory:'Inventory',accounting:'Accounting',facilities:'Facilities',customer_service:'Customer Service',system:'Desk',human:'Human'}
export const initials:{[key:string]:string}={boss:'BO',inventory:'IN',accounting:'AC',facilities:'FA',customer_service:'CS',system:'CC',human:'YOU'}
export const money=(n:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n)
