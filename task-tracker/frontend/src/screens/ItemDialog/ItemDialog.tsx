import { useEffect, useState } from 'react';
import { auth, date, dateTime, hours, json, request, typeName } from '../../api';
import type { Item, Json } from '../../api';
import { AttachmentFrame } from '../../AttachmentFrame';
import { Empty } from '../../components/Empty';
import { ErrorBanner } from '../../components/ErrorBanner';
import { WorkItemPicker } from '../../components/WorkItemPicker';
import { CreateItem } from './CreateItem';
import { can, selectName } from '../../context';
import type { Context } from '../../context';

const iso = (value: unknown) => (value ? String(value).slice(0, 10) : '');
const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function ItemDialog({ id, context, close, open, refresh }:
  { id: string; context: Context; close: () => void; open: (id: string) => void; refresh: () => void }) {
  const [item, setItem] = useState<Item | null>(null);
  const [form, setForm] = useState<Json>({});
  const [comments, setComments] = useState<Array<Json>>([]);
  const [logs, setLogs] = useState<Array<Json>>([]);
  const [attachments, setAttachments] = useState<Array<Json>>([]);
  const [preview, setPreview] = useState<{ name: string; url: string; type: string } | null>(null);
  const [history, setHistory] = useState<Array<Json>>([]);
  const [tab, setTab] = useState<'discussion' | 'time' | 'files' | 'history'>('discussion');
  const [error, setError] = useState('');
  const [comment, setComment] = useState('');
  const [logHours, setLogHours] = useState('');
  const [logDate, setLogDate] = useState(new Date().toISOString().slice(0, 10));
  const [childForm, setChildForm] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const bump = () => setReloadToken(value => value + 1);

  useEffect(() => {
    let active = true;
    Promise.all([
      request<Item>(`/work-items/${id}`), request<Array<Json>>(`/work-items/${id}/comments`),
      request<Array<Json>>(`/work-items/${id}/time-logs`), request<Array<Json>>(`/work-items/${id}/attachments`),
      request<Array<Json>>(`/work-items/${id}/history`),
    ]).then(([data, discussion, time, files, audit]) => {
      if (!active) return;
      setItem(data); setComments(discussion); setLogs(time); setAttachments(files); setHistory(audit);
      const draft = localStorage.getItem(`description:${id}`);
      setForm({ title: data.title, description: draft ?? data.description, statusId: data.statusId, priorityId: data.priorityId,
        assigneeId: data.assigneeId || '', startDate: iso(data.startDate), dueDate: iso(data.dueDate),
        plannedHours: data.children.length || ['PROJECT', 'EPIC'].includes(data.type) ? '' : String(data.plannedHours),
        parentId: data.parentId || '' });
    }).catch(e => { if (active) setError(getError(e)); });
    return () => { active = false; };
  }, [id, reloadToken]);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [close]);

  const set = (key: string, value: unknown) => {
    setForm(current => ({ ...current, [key]: value }));
    if (key === 'description') localStorage.setItem(`description:${id}`, String(value));
  };
  const save = async () => {
    if (!item) return;
    try {
      await request(`/work-items/${id}`, json('PATCH', { ...form, assigneeId: form.assigneeId || null, parentId: form.parentId || null,
        startDate: form.startDate || null, dueDate: form.dueDate || null, plannedHours: form.plannedHours || null, version: item.version }));
      localStorage.removeItem(`description:${id}`); bump(); refresh();
    } catch (e) { setError(getError(e)); }
  };
  const remove = async () => {
    if (!item) return;
    if (item.children.length > 0) { alert(`Нельзя удалить: сначала перенесите или удалите ${item.children.length} дочерних элементов.`); return; }
    if (!confirm(`Безвозвратно удалить «${item.title}»?`)) return;
    try { await request(`/work-items/${id}`, { method: 'DELETE', headers: { 'X-Confirm-Hard-Delete': id } }); close(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const sendComment = async () => {
    if (!comment.trim()) return;
    try { await request(`/work-items/${id}/comments`, json('POST', { body: comment })); setComment(''); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const sendTime = async () => {
    try { await request(`/work-items/${id}/time-logs`, json('POST', { hours: logHours, loggedDate: logDate })); setLogHours(''); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const upload = async (file: File) => {
    try { const data = new FormData(); data.append('file', file); await request(`/work-items/${id}/attachments`, { method: 'POST', body: data }); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const download = async (a: Json) => {
    try {
      const user = await auth.getUser();
      const response = await fetch(`/api/v1/work-items/${id}/attachments/${a.id}`, { headers: { Authorization: `Bearer ${user?.access_token}` } });
      if (!response.ok) throw new Error('Не удалось скачать вложение');
      const blob = await response.blob(); const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = String(a.fileName); link.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(getError(e)); }
  };
  const showPreview = async (a: Json) => {
    try {
      const user = await auth.getUser();
      const response = await fetch(`/api/v1/work-items/${id}/attachments/${a.id}`, { headers: { Authorization: `Bearer ${user?.access_token}` } });
      if (!response.ok) throw new Error('Не удалось открыть вложение');
      const blob = await response.blob();
      setPreview({ name: String(a.fileName), type: String(a.contentType), url: URL.createObjectURL(blob) });
    } catch (e) { setError(getError(e)); }
  };
  const removeAttachment = async (a: Json) => {
    if (!confirm('Удалить вложение?')) return;
    try { await request(`/work-items/${id}/attachments/${a.id}`, { method: 'DELETE' }); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const removeComment = async (c: Json) => {
    if (!confirm('Удалить комментарий?')) return;
    try { await request(`/work-items/${id}/comments/${c.id}`, { method: 'DELETE' }); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const editComment = async (c: Json) => {
    const value = prompt('Изменить комментарий', String(c.body));
    if (value === null) return;
    try { await request(`/work-items/${id}/comments/${c.id}`, json('PATCH', { body: value })); bump(); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const allowedChild = item?.type === 'PROJECT' ? 'EPIC' : item?.type === 'EPIC' ? 'TASK' : ['TASK', 'BUG'].includes(item?.type || '') ? 'SUBTASK' : null;

  return <div className="overlay" onMouseDown={close}>
    <div className="item-dialog" role="dialog" aria-modal="true" aria-label="Карточка рабочего элемента" onMouseDown={e => e.stopPropagation()}>
      <div className="dialog-title">
        <div><span className="eyebrow">{item ? `${typeName(item.type)} · ${id.slice(0, 8)}` : 'ЗАГРУЗКА'}</span><h2>{item?.title || 'Рабочий элемент'}</h2></div>
        <button onClick={close} aria-label="Закрыть">×</button>
      </div>
      <ErrorBanner message={error} clear={() => setError('')} />
      {item && <div className="dialog-scroll">
        <div className="summary-strip">
          <div><small>План</small><strong>{hours(item.plannedHours)}</strong></div>
          <div><small>Факт</small><strong>{hours(item.actualHours)}</strong></div>
          <div><small>Остаток</small><strong className={item.remainingHours < 0 ? 'negative' : ''}>{hours(item.remainingHours)}</strong></div>
          <div><small>Версия</small><strong>#{item.version}</strong></div>
        </div>
        <div className="form-grid item-fields">
          <label>Название<input value={String(form.title ?? '')} onChange={e => set('title', e.target.value)} disabled={!can(context, 'item.update')} /></label>
          <label>Статус<select value={String(form.statusId ?? '')} onChange={e => set('statusId', e.target.value)} disabled={!can(context, 'item.update') || !can(context, 'item.status')}>
            {context.statuses.filter(s => s.active || s.id === item.statusId).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></label>
          <label className="span-2">Описание (Markdown)<textarea rows={5} value={String(form.description ?? '')} onChange={e => set('description', e.target.value)} disabled={!can(context, 'item.update')} />
            <small>Черновик сохраняется в этом браузере до нажатия «Сохранить»</small></label>
          <label>Приоритет<select value={String(form.priorityId ?? '')} onChange={e => set('priorityId', e.target.value)} disabled={!can(context, 'item.update')}>
            {context.priorities.filter(p => p.active || p.id === item.priorityId).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select></label>
          <label>Исполнитель<select value={String(form.assigneeId ?? '')} onChange={e => set('assigneeId', e.target.value)} disabled={!can(context, 'item.update')}>
            <option value="">Не назначен</option>
            {context.users.filter(u => u.active || u.id === item.assigneeId).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select></label>
          <label>Дата начала<input type="date" value={String(form.startDate ?? '')} onChange={e => set('startDate', e.target.value)} disabled={!can(context, 'item.update')} /></label>
          <label>Срок<input type="date" value={String(form.dueDate ?? '')} onChange={e => set('dueDate', e.target.value)} disabled={!can(context, 'item.update')} /></label>
          <label>Плановая оценка, ч<input type="number" step="0.01" min="0" value={String(form.plannedHours ?? '')} onChange={e => set('plannedHours', e.target.value)}
            disabled={!can(context, 'item.update') || item.children.length > 0 || ['PROJECT', 'EPIC'].includes(item.type)} /></label>
          <label>Родительский элемент
            <WorkItemPicker value={String(form.parentId ?? '')} onChange={value => set('parentId', value)} excludeId={id} placeholder="Начните вводить название…" />
          </label>
          <div className="span-2 field-note">Итерация: {item.iterationId || 'не назначена'}{item.unestimatedLeaves > 0 && <span className="warning"> · Есть элементы без оценки: {item.unestimatedLeaves}</span>}</div>
        </div>
        <div className="hierarchy">
          <div className="mini-head"><h3>Иерархия</h3>{allowedChild && can(context, 'item.create') && <button className="text-button" onClick={() => setChildForm(true)}>＋ Дочерний элемент</button>}</div>
          {item.parentId && <button className="link-row" onClick={() => open(item.parentId!)}>↑ Родительский элемент · {item.parentId.slice(0, 8)}</button>}
          {item.children.length ? item.children.map(child => <button className="link-row" key={child.id} onClick={() => open(child.id)}>↳ {typeName(child.type)} · {child.title}</button>) : <p className="muted">Дочерних элементов нет</p>}
        </div>
        <div className="tabs" role="tablist">
          {([['discussion', 'Комментарии'], ['time', 'Трудозатраты'], ['files', 'Вложения'], ['history', 'История']] as const).map(([key, label]) =>
            <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}
        </div>
        {tab === 'discussion' && <div className="tab-body"><div className="stack">
          {comments.length ? comments.map(c => <div className="activity" key={String(c.id)}>
            <div className="activity-meta"><strong>{selectName(context.users, String(c.authorId))}</strong><small>{dateTime(c.createdAt)}</small></div>
            <p>{String(c.body)}</p>
            {(c.authorId === context.userId || can(context, 'comment.manage')) && <div className="inline-actions"><button onClick={() => void editComment(c)}>Изменить</button><button onClick={() => void removeComment(c)}>Удалить</button></div>}
          </div>) : <Empty text="Комментариев пока нет" />}
        </div>{can(context, 'comment.create') && <div className="composer"><textarea placeholder="Написать комментарий" value={comment} onChange={e => setComment(e.target.value)} /><button className="button primary" onClick={() => void sendComment()}>Отправить</button></div>}</div>}
        {tab === 'time' && <div className="tab-body"><div className="stack">
          {logs.length ? logs.map(log => <div className="activity" key={String(log.id)}><strong>{hours(log.hours)}</strong> · {date(log.loggedDate)} · {selectName(context.users, String(log.userId))}{Boolean(log.comment) && <p>{String(log.comment)}</p>}</div>) : <Empty text="Записей времени пока нет" />}
        </div>{can(context, 'time.create') && item.children.length === 0 && !['PROJECT', 'EPIC'].includes(item.type) &&
          <div className="composer row"><input type="date" value={logDate} onChange={e => setLogDate(e.target.value)} /><input aria-label="Часы" type="number" min="0.01" step="0.01" placeholder="Часы" value={logHours} onChange={e => setLogHours(e.target.value)} /><button className="button primary" onClick={() => void sendTime()}>Добавить время</button></div>}</div>}
        {tab === 'files' && <div className="tab-body"><div className="stack">
          {attachments.length ? attachments.map(a => <div className="file-row" key={String(a.id)}>
            <div><strong>{String(a.fileName)}</strong><small>{Math.round(Number(a.sizeBytes) / 1024)} КБ · {dateTime(a.uploadedAt)}</small></div>
            <div className="inline-actions">{(/^(image\/|text\/|application\/pdf$)/).test(String(a.contentType)) && <button onClick={() => void showPreview(a)}>Просмотр</button>}<button onClick={() => void download(a)}>Скачать</button>{can(context, 'attachment.delete') && <button onClick={() => void removeAttachment(a)}>Удалить</button>}</div>
          </div>) : <Empty text="Вложений пока нет" />}
        </div>{can(context, 'attachment.create') && <label className="button secondary file-button">＋ Прикрепить файл<input type="file" onChange={e => { const file = e.target.files?.[0]; if (file) void upload(file); e.target.value = ''; }} /></label>}
          {preview && <div className="attachment-preview"><div className="mini-head"><strong>{preview.name}</strong><button onClick={() => setPreview(null)}>Закрыть</button></div>{preview.type.startsWith('image/') ? <img src={preview.url} alt={preview.name} /> : <AttachmentFrame name={preview.name} url={preview.url} />}</div>}</div>}
        {tab === 'history' && <div className="tab-body"><div className="stack">
          {history.length ? history.map(entry => <details className="activity" key={String(entry.id)}>
            <summary><strong>{String(entry.actorId || entry.externalSource || 'Система')}</strong><small>{dateTime(entry.occurredAt)}</small></summary>
            <div className="diff-grid">{Object.entries(typeof entry.newValues === 'string' ? JSON.parse(entry.newValues) : entry.newValues as Json).map(([key, value]) =>
              <div className="diff-row" key={key}><strong>{key}</strong><del>{String((typeof entry.oldValues === 'string' ? JSON.parse(entry.oldValues) : entry.oldValues as Json)?.[key] ?? '—')}</del><ins>{String(value ?? '—')}</ins></div>)}</div>
          </details>) : <Empty text="Истории изменений пока нет" />}
        </div></div>}
        <div className="dialog-actions sticky">
          {can(context, 'item.delete') && <button className="button danger" onClick={() => void remove()}>Безвозвратно удалить</button>}
          {can(context, 'item.update') && <button className="button primary" onClick={() => void save()}>Сохранить изменения</button>}
          <button className="button secondary" onClick={close}>Закрыть</button>
        </div>
      </div>}
      {childForm && allowedChild && <CreateItem context={context} parentId={id} suggestedType={allowedChild} close={() => setChildForm(false)} created={childId => { setChildForm(false); refresh(); open(childId); }} />}
    </div>
  </div>;
}
