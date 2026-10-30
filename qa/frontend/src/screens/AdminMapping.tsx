import { useEffect, useState } from 'react';
import { TrackerStatusMappingItem, getTrackerMapping, replaceTrackerMapping } from '../api/admin';
import { ErrorMessage } from '../components/ErrorMessage';
import { useToast } from '../components/Toast';
import { formatDateTime, statusLabel } from '../labels';
import { useLoad } from '../useLoad';

type Row = TrackerStatusMappingItem & { draftId: number; updatedBy?: string; updatedAt?: string };

// Статусы тестирования ведёт QA System: сопоставить с ними статус Task Tracker нельзя (ADR-008).
const MAPPABLE = ['OPEN', 'IN_PROGRESS', 'FIXED'] as const;

let nextRowId = 1;

export function AdminMapping() {
  const toast = useToast();
  const mapping = useLoad(() => getTrackerMapping(), ['mapping']);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (mapping.data) setRows(mapping.data.items.map((item) => ({ ...item, draftId: nextRowId++ })));
  }, [mapping.data]);

  const patch = (draftId: number, value: Partial<Row>) => setRows(rows.map((row) => (row.draftId === draftId ? { ...row, ...value } : row)));
  const incomplete = rows.some((row) => !row.trackerStatusId.trim() || !row.trackerStatusName.trim());

  const save = async () => {
    setError(null);
    setSaving(true);
    try {
      mapping.setData(await replaceTrackerMapping(rows.map(({ trackerStatusId, trackerStatusName, qaStatus, requiresAssignee, isActive }) => ({ trackerStatusId, trackerStatusName, qaStatus, requiresAssignee, isActive }))));
      toast('Таблица маппинга сохранена');
    } catch (failure) {
      setError(failure);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <p className="muted">Сохраняется вся таблица: удалённые строки исчезают. Статусы тестирования ведёт QA System, поэтому сопоставить можно только статусы разработки.</p>
      <ErrorMessage error={error} />
      <ErrorMessage error={mapping.error} onRetry={mapping.reload} />
      <div className="panel">
        <table aria-busy={mapping.loading && !mapping.data}>
          <thead><tr><th>ID статуса Task Tracker</th><th>Название</th><th>Статус QA System</th><th>Нужен исполнитель</th><th>Активно</th><th>Изменил</th><th /></tr></thead>
          <tbody>
            {mapping.loading && !mapping.data && <tr><td colSpan={7}><span className="skeleton" /></td></tr>}
            {mapping.data && rows.length === 0 && <tr><td colSpan={7}><div className="empty">Таблица пуста</div></td></tr>}
            {rows.map((row, index) => (
              <tr key={row.draftId}>
                <td><input type="text" aria-label={`ID статуса, строка ${index + 1}`} value={row.trackerStatusId} onChange={(event) => patch(row.draftId, { trackerStatusId: event.target.value })} /></td>
                <td><input type="text" aria-label={`Название, строка ${index + 1}`} value={row.trackerStatusName} onChange={(event) => patch(row.draftId, { trackerStatusName: event.target.value })} /></td>
                <td>
                  <select aria-label={`Статус QA System, строка ${index + 1}`} value={row.qaStatus ?? ''} onChange={(event) => patch(row.draftId, { qaStatus: (event.target.value || null) as Row['qaStatus'] })}>
                    <option value="">Не меняет дефект</option>
                    {MAPPABLE.map((value) => <option key={value} value={value}>{statusLabel(value, 'defect')}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" aria-label={`Нужен исполнитель, строка ${index + 1}`} checked={row.requiresAssignee ?? false} onChange={(event) => patch(row.draftId, { requiresAssignee: event.target.checked })} /></td>
                <td><input type="checkbox" aria-label={`Активно, строка ${index + 1}`} checked={row.isActive ?? true} onChange={(event) => patch(row.draftId, { isActive: event.target.checked })} /></td>
                <td className="muted">{row.updatedBy ? `${row.updatedBy}, ${formatDateTime(row.updatedAt)}` : 'новая строка'}</td>
                <td><button type="button" aria-label={`Удалить строку ${index + 1}`} onClick={() => setRows(rows.filter((item) => item.draftId !== row.draftId))}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button type="button" onClick={() => setRows([...rows, { draftId: nextRowId++, trackerStatusId: '', trackerStatusName: '', qaStatus: null, requiresAssignee: false, isActive: true }])}>Добавить строку</button>
          <button type="button" className="primary" disabled={saving || incomplete} onClick={save}>Сохранить таблицу</button>
        </div>
      </div>
    </>
  );
}
