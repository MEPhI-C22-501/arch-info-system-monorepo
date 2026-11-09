import { useState } from 'react';
import { json, request } from './api';
import type { Item, Iteration } from './api';
import type { Context } from './context';
export function BulkActions({ items, context, iterations, refresh, completed }: { items: Item[]; context: Context; iterations: Iteration[]; refresh: () => void; completed: (ids:string[])=>void }) {
  const [operation,setOperation]=useState('status'); const [value,setValue]=useState('');
  const [busy,setBusy]=useState(false); const [result,setResult]=useState('');
  const run=async () => {
    setBusy(true);
    try {
      const data=await request<{results:Array<{id:string;success:boolean;errors?:Array<{reason:string}>}>}>('/work-items/bulk',json('POST',{operation,value:value || null,items:items.map(({id,version})=>({id,version}))}));
      setResult(data.results.map(row=>`${items.find(i=>i.id===row.id)?.title}: ${row.success?'готово':row.errors?.map(e=>e.reason).join(', ')}`).join('; ')); completed(data.results.filter(row=>row.success).map(row=>row.id)); refresh();
    } catch(e) { setResult(String(e)); } finally { setBusy(false); }
  };
  const options=operation==='status'?context.statuses.filter(s=>s.active):operation==='assignee'?context.users.filter(u=>u.active):iterations.filter(i=>i.state!=='COMPLETED');
  return <div className="panel bulk-actions"><strong>Выбрано: {items.length}</strong>
    <div className="actions">
      <select aria-label="Массовая операция" value={operation} onChange={e=>{setOperation(e.target.value);setValue('');}}><option value="status">Статус</option><option value="assignee">Исполнитель</option><option value="iteration">Итерация</option></select>
      <select aria-label="Новое значение" value={value} onChange={e=>setValue(e.target.value)}><option value="">{operation==='status'?'Выберите статус':'Не назначено'}</option>{options.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select>
      <button className="button primary" disabled={busy || !items.length || items.length>100 || (operation==='status'&&!value)} onClick={()=>void run()}>Применить</button>
    </div>
    <p role="status" className="muted">{result}</p>
  </div>;
}
