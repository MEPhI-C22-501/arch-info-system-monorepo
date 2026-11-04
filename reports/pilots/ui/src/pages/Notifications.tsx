import { useState } from 'react';
import { api, downloadBlob, errorMessage } from '../api';
import { Empty, Failure, Loading } from '../components/State';
import { dateTime } from '../format';
import { useSession } from '../session';
import type { ExportJob, Notification } from '../types';
import type { Loaded } from '../useLoad';

const KINDS: Record<string, string> = {
  EXPORT_READY: 'Выгрузка готова',
  SCHEDULED_REPORT_READY: 'Регламентный отчёт сформирован',
  RECIPIENT_SKIPPED: 'Получатель пропущен: нет доступа к отчёту',
  SUBSCRIPTION_PAUSED: 'Подписка приостановлена: у владельца больше нет доступа',
};

// SCR-11. The list is loaded once in the app shell, which also shows the unread badge.
export function Notifications({ notifications }: { notifications: Loaded<{ items: Notification[] }> }) {
  const { token } = useSession();
  const [error, setError] = useState('');
  const act = async (action: () => Promise<void>) => {
    try { await action(); notifications.reload(); } catch (e) { setError(errorMessage(e)); }
  };
  const open = (item: Notification) => act(async () => {
    const id = item.exportId ?? item.snapshotId;
    if (id) {
      const job = await api<ExportJob>(token, 'exports/' + id);
      downloadBlob(await api<Blob>(token, `exports/${id}/file`), `${job.reportId}-${id}.${job.format}`);
    }
    if (!item.readAt) await api(token, 'notifications/' + item.notificationId, 'PATCH', { read: true });
  });
  const items = notifications.data?.items ?? [];
  return (
    <>
      <h1>Уведомления</h1>
      {error && <Failure message={error} />}
      {notifications.loading && !notifications.data ? <Loading /> : notifications.error ? <Failure message={errorMessage(notifications.error)} onRetry={notifications.reload} /> :
        !items.length ? <Empty>Уведомлений нет.</Empty> : (
          <ul className="list">
            {items.map((item) => (
              <li key={item.notificationId} className={item.readAt ? 'read' : 'unread'}>
                <span>
                  {!item.readAt && <span className="visually-hidden">Новое: </span>}
                  {KINDS[item.kind] ?? item.kind} · {dateTime(item.createdAt)}
                </span>
                <span className="button-row">
                  {(item.exportId || item.snapshotId) && <button type="button" onClick={() => open(item)}>Скачать файл</button>}
                  {!item.readAt && <button type="button" className="secondary" onClick={() => act(() => api(token, 'notifications/' + item.notificationId, 'PATCH', { read: true }))}>Прочитано</button>}
                </span>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
