import { useState } from 'react';
import { json, request } from '../api';
import type { Context } from '../context';
import { can } from '../context';
import { useApiResource } from '../hooks/useApiResource';
import { WorkItemPicker } from './WorkItemPicker';
export function Links({ id, context, open }: { id:string; context:Context; open:(id:string)=>void }) {
  const [revision,setRevision]=useState(0); const [target,setTarget]=useState(''); const [type,setType]=useState('RELATED'); const [error,setError]=useState('');
  const {data,error:loadError}=useApiResource<Array<{id:string;targetId:string;title:string;type:string;outgoing:boolean}>>(`/work-items/${id}/links`,revision);
  const run=async (path:string,init:RequestInit) => { try { await request(path,init);setRevision(v=>v+1);setError(''); } catch(e) {setError(String(e));} };
  return <section><h3>Связи задач</h3>{(error||loadError)&&<p role="alert">{error||loadError}</p>}
    {data?.map(link=><div key={link.id} className="link-item"><button className="link-row" onClick={()=>open(link.targetId)}>{link.type==='RELATED'?'Связано':link.outgoing?'Блокирует':'Заблокировано'}: {link.title}</button>{can(context,'item.update')&&<button className="link-item-remove" aria-label={`Удалить связь ${link.title}`} onClick={()=>void run(`/work-items/${id}/links/${link.id}`,{method:'DELETE'})}>×</button>}</div>)}
    {can(context,'item.update')&&<div className="actions"><WorkItemPicker value={target} onChange={setTarget} /><select aria-label="Тип связи" value={type} onChange={e=>setType(e.target.value)}><option value="RELATED">Связано</option><option value="BLOCKS">Блокирует</option></select><button className="button secondary" disabled={!target} onClick={()=>void run(`/work-items/${id}/links`,json('POST',{targetId:target,type}))}>Добавить связь</button></div>}
  </section>;
}

export function CardLinks({ id, open }: {id:string;open:(id:string)=>void}) {
  const {data}=useApiResource<Array<{id:string;targetId:string;title:string;type:string;outgoing:boolean}>>(`/work-items/${id}/links`);
  return <div onClick={e=>e.stopPropagation()} onKeyDown={e=>e.stopPropagation()}>{data?.map(link=><button key={link.id} className="link-summary" onClick={()=>open(link.targetId)}>{link.type==='RELATED'?'↔':link.outgoing?'Блокирует':'Зависит от'} {link.title}</button>)}</div>;
}
