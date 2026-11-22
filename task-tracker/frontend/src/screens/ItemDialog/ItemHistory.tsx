import { date, dateTime, hours } from '../../api';
import type { Iteration, Json } from '../../api';
import { Empty } from '../../components/Empty';
import type { Context } from '../../context';
import { useApiResource } from '../../hooks/useApiResource';
import { describeHistoryEntry } from './historyDiff';
import type { HistoryEntry, HistoryNames } from './historyDiff';

const namesOf = (rows: ReadonlyArray<{ id: string; name: string }>) => new Map(rows.map(row => [row.id, row.name]));

export function ItemHistory({ history, context, attachments, logs }: {
  history: HistoryEntry[];
  context: Context;
  attachments: Json[];
  logs: Json[];
}) {
  const { data: iterations } = useApiResource<Iteration[]>(
    context.permissions.includes('iteration.read') ? '/iterations' : null,
  );
  const names: HistoryNames = {
    statuses: namesOf(context.statuses),
    priorities: namesOf(context.priorities),
    users: namesOf(context.users),
    iterations: namesOf(iterations ?? []),
    attachments: new Map(attachments.map(row => [String(row.id), String(row.fileName)])),
    timeLogs: new Map(logs.map(row => [String(row.id), `${hours(row.hours)} · ${date(row.loggedDate)}`])),
  };

  const events = history.map(entry => ({ entry, ...describeHistoryEntry(entry, names) }))
    .filter(event => event.visible).reverse();
  if (!events.length) return <Empty text="Истории изменений пока нет" />;

  return <div className="history-list">
    {events.map(({ entry, actor, title, changes, actions }) => {
      const eventDetails = actions.filter(action => action.detail || action.label !== title);
      const heading = <span className="history-summary-content">
        <span className="history-heading"><strong>{title}</strong><small>{actor}</small></span>
        <time dateTime={entry.occurredAt}>{dateTime(entry.occurredAt)}</time>
      </span>;
      if (!changes.length && !eventDetails.length) {
        return <div className="activity" key={entry.id}>{heading}</div>;
      }
      return <details className="activity" key={entry.id} open>
        <summary className="history-summary">{heading}</summary>
        <div className="history-changes">
          {eventDetails.map(action => <p className="history-action" key={action.key}>
            {action.label === title ? action.detail : <>{action.label}{action.detail && <> · {action.detail}</>}</>}
          </p>)}
          {changes.map(change => <div className="history-change" key={change.field}>
            <strong>{change.label}</strong>
            <div className="history-values">
              <div className="history-before"><span>Было</span><del>{change.before}</del></div>
              <div className="history-after"><span>Стало</span><ins>{change.after}</ins></div>
            </div>
          </div>)}
        </div>
      </details>;
    })}
  </div>;
}
