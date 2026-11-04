import { useEffect, useState } from 'react';
import { api, downloadBlob, errorMessage } from '../api';
import { Empty, Failure, Loading } from '../components/State';
import { dateTime } from '../format';
import { useSession } from '../session';
import type { ExportJob, ExportStatus, Page } from '../types';
import { useLoad } from '../useLoad';

const STATUS: Record<ExportStatus, string> = {
  CREATED: 'Создано', QUEUED: 'В очереди', RUNNING: 'Формируется', COMPLETED: 'Готово', DELIVERED: 'Доставлено', FAILED: 'Ошибка', EXPIRED: 'Срок хранения истёк',
};

// SCR-08.
export function Exports() {
  const { token } = useSession();
  const jobs = useLoad(() => api<Page<ExportJob>>(token, 'exports'), [token]);
  const [error, setError] = useState('');
  const pending = (jobs.data?.items ?? []).some((j) => j.status === 'CREATED' || j.status === 'QUEUED' || j.status === 'RUNNING');
  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(jobs.reload, 3000);
    return () => clearTimeout(timer);
  }, [pending, jobs]);

  const download = async (job: ExportJob) => {
    try {
      downloadBlob(await api<Blob>(token, `exports/${job.exportId}/file`), `${job.reportId}-${job.exportId}.${job.format}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <>
      <h1>Выгрузки</h1>
      <button type="button" className="secondary" onClick={jobs.reload}>Обновить</button>
      {error && <Failure message={error} />}
      {jobs.loading && !jobs.data ? <Loading /> : jobs.error ? <Failure message={errorMessage(jobs.error)} onRetry={jobs.reload} /> :
        !jobs.data?.items.length ? <Empty>Выгрузок пока нет. Их создают кнопки «Выгрузить» на странице отчёта.</Empty> : (
          <div className="table-scroll" tabIndex={0}>
            <table>
              <caption>Задания выгрузки</caption>
              <thead><tr><th scope="col">Отчёт</th><th scope="col">Формат</th><th scope="col">Статус</th><th scope="col">Создано</th><th scope="col">Хранится до</th><th scope="col">Действие</th></tr></thead>
              <tbody>
                {jobs.data.items.map((job) => (
                  <tr key={job.exportId}>
                    <td>{job.reportId}</td>
                    <td>{job.format.toUpperCase()}</td>
                    <td className={'status status-' + job.status.toLowerCase()}>{STATUS[job.status] ?? job.status}{job.error ? ': ' + job.error : ''}</td>
                    <td>{dateTime(job.createdAt)}</td>
                    <td>{dateTime(job.expiresAt)}</td>
                    <td>{(job.status === 'COMPLETED' || job.status === 'DELIVERED') && <button type="button" onClick={() => download(job)}>Скачать</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </>
  );
}
