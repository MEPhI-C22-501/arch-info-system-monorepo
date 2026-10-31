import { FormEvent, useState } from 'react';
import { Link, useParams } from 'react-router';
import type { Severity } from '../api/client';
import { DefectHistoryEntry, DefectStatus, addDefectComment, getDefect, listDefectHistory, transitionDefect, updateDefect } from '../api/defects';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field, Prop } from '../components/Field';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { SEVERITIES, formatDateTime, statusLabel } from '../labels';
import { canCommentDefect, canEditDefect, defectTransitions } from '../permissions';
import { useSession } from '../session';
import { useLoad } from '../useLoad';

const HISTORY_COLUMNS: Column<DefectHistoryEntry>[] = [
  { header: 'Когда', render: (row) => formatDateTime(row.occurredAt) },
  { header: 'Кто', render: (row) => row.author },
  { header: 'Источник', render: (row) => row.source },
  { header: 'Поле', render: (row) => row.field },
  { header: 'Было', render: (row) => row.oldValue ?? '' },
  { header: 'Стало', render: (row) => row.newValue ?? '' },
];

const isWebLink = (url?: string | null): url is string => !!url && /^https?:\/\//.test(url);

export function DefectCard() {
  const { id = '' } = useParams();
  const { role } = useSession();
  const toast = useToast();
  const defect = useLoad(() => getDefect(id), [id]);
  const history = useLoad(() => listDefectHistory(id), [id]);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (!defect.data) return defect.error ? <ErrorMessage error={defect.error} onRetry={defect.reload} /> : <p className="muted" aria-busy="true">Загрузка…</p>;
  const current = defect.data;
  const moves = defectTransitions(role, current.status);

  const guarded = async (action: () => Promise<void>) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      history.reload();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  };

  const move = (to: DefectStatus) => guarded(async () => {
    defect.setData(await transitionDefect(id, to));
    toast(`Статус: ${statusLabel(to, 'defect')}. Запись добавлена в историю`);
  });

  const changeSeverity = (severity: Severity) => guarded(async () => {
    defect.setData(await updateDefect(id, { severity }));
    toast(`Серьёзность: ${severity}`);
  });

  const submitComment = (event: FormEvent) => {
    event.preventDefault();
    if (!comment.trim()) return;
    void guarded(async () => {
      await addDefectComment(id, comment.trim());
      setComment('');
      defect.reload();
      toast('Комментарий добавлен');
    });
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/defects">← К списку</Link></div>
      <h2>{current.key} <StatusBadge status={current.status} kind="defect" /> <StatusBadge status={current.severity} /></h2>
      <p>{current.title}</p>
      <div className="bar">
        {moves.length
          ? moves.map((to) => <button key={to} type="button" className="primary" disabled={busy} onClick={() => move(to)}>→ {statusLabel(to, 'defect')}</button>)
          : <span className="muted">Для вашей роли переходов из этого статуса нет</span>}
        {canEditDefect(role) && (
          <label className="filter" style={{ marginLeft: 'auto' }}>
            Серьёзность
            <select value={current.severity} disabled={busy} onChange={(event) => changeSeverity(event.target.value as Severity)}>
              {SEVERITIES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        )}
      </div>
      <ErrorMessage error={error} />
      {current.trackerMismatch && <div className="notice warn">Статусы систем расходятся: сверьте дефект и «Ошибку» в Task Tracker.</div>}
      <div className="panel">
        <dl className="props">
          <Prop name="Происхождение">{current.origin === 'AUTO' ? 'Автодефект' : 'Вручную'}</Prop>
          <Prop name="Автор">{current.author}</Prop>
          <Prop name="Кейс">{current.testCaseId && <><Link to={`/test-cases/${current.testCaseId}`}>{current.testCaseKey}</Link>{current.caseVersion ? `, версия ${current.caseVersion}` : ''}</>}</Prop>
          <Prop name="Окружение">{current.environment}</Prop>
          <Prop name="Версия сборки">{current.buildVersion}</Prop>
          <Prop name="Шаги воспроизведения"><pre>{current.reproSteps}</pre></Prop>
          <Prop name="Ожидаемый результат">{current.expectedResult}</Prop>
          <Prop name="Фактический результат">{current.actualResult}</Prop>
          <Prop name="Приоритет (предложенный)">{current.priority}</Prop>
          <Prop name="Прогоны">
            {current.runs.length > 0 && current.runs.map((link, index) => (
              <span key={link.resultId}>{index > 0 && ', '}<Link to={`/runs/${link.runId}`}>{link.runKey}</Link></span>
            ))}
          </Prop>
          <Prop name="Переоткрытий">{String(current.reopenCount)}</Prop>
          <Prop name="Создан">{formatDateTime(current.createdAt)}</Prop>
        </dl>
      </div>
      <div className="panel">
        <h3>Task Tracker <span className="muted">(только чтение)</span></h3>
        <dl className="props">
          <Prop name="Синхронизация"><StatusBadge status={current.trackerSyncState} /></Prop>
          <Prop name="«Ошибка»">{isWebLink(current.trackerWorkItemUrl) ? <a href={current.trackerWorkItemUrl} target="_blank" rel="noreferrer">{current.trackerWorkItemId ?? current.trackerWorkItemUrl}</a> : current.trackerWorkItemId}</Prop>
          <Prop name="Статус">{current.trackerStatus}</Prop>
          <Prop name="Приоритет">{current.trackerPriority}</Prop>
          <Prop name="Исполнитель">{current.trackerAssignee}</Prop>
        </dl>
      </div>
      <div className="panel">
        <h3>История</h3>
        <DataTable
          columns={HISTORY_COLUMNS}
          rows={history.data?.items}
          rowKey={(row) => `${row.occurredAt}:${row.field}:${row.newValue}`}
          loading={history.loading}
          error={history.error}
          onRetry={history.reload}
          emptyText="Записей нет"
        />
      </div>
      <div className="panel">
        <h3>Комментарии</h3>
        {current.comments.length === 0 && <p className="muted">Комментариев нет</p>}
        {current.comments.map((item) => (
          <p key={item.id}>
            <span className="muted">{formatDateTime(item.createdAt)} · {item.author}{item.source === 'TRACKER' ? ' · из Task Tracker' : ''}</span><br />
            {item.body}
          </p>
        ))}
        {canCommentDefect(role) && (
          <form onSubmit={submitComment}>
            <Field label="Новый комментарий"><textarea rows={2} value={comment} onChange={(event) => setComment(event.target.value)} /></Field>
            <button type="submit" disabled={busy || !comment.trim()}>Добавить комментарий</button>
          </form>
        )}
      </div>
    </>
  );
}
