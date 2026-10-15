import type {Desk,Event} from './types'
const BASE='http://localhost:8000'
async function request<T>(path:string,body?:unknown):Promise<T>{
 const response=await fetch(BASE+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Desk-Action':'human'},body:body===undefined?undefined:JSON.stringify(body)})
 const data=await response.json()
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The request could not be completed.')
 return data as T
}
export const api={desk:()=>request<Desk>('/api/desk'),events:(after:number)=>request<Event[]>('/api/events?after='+after),run:(id:number)=>request('/api/tickets/'+id+'/run',{}),review:(id:number)=>request('/api/tickets/'+id+'/review',{}),decide:(id:string,approve:boolean,approved_by:string)=>request('/api/approvals/'+id+'/decide',{approve,approved_by}),reset:()=>request('/api/reset',{confirm:'RESET WORKING DATABASE'}),export:()=>request('/api/export',{})}
