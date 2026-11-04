import { useEffect, useRef } from 'react';
import { ApiError, api, errorMessage } from '../api';
import { drillQuery, nextSlice, type DrillStep } from '../drill';
import { NOT_SET, SLICE_TITLES } from '../format';
import { useSession } from '../session';
import type { DimensionValue, ReportDefinition, ReportQuery, ReportResult } from '../types';
import { useLoad } from '../useLoad';
import { ResultTable } from './ResultTable';
import { Empty, Failure, Loading, Notice } from './State';

// SCR-03: path[0] is the clicked row of the main table, every next step a row of the level below.
// The panel shows the next level; the last one ('record') is the source records.
export function DrillPanel({ report, query, path, onPath }: {
  report: ReportDefinition; query: ReportQuery; path: DrillStep[]; onPath: (path: DrillStep[]) => void;
}) {
  const { token } = useSession();
  const used = path.map((s) => s.slice);
  const next = nextSlice(report.slices, used);
  const result = useLoad<ReportResult | null>(
    () => (next ? api<ReportResult>(token, `reports/${report.reportId}/drilldown`, 'POST', drillQuery(query, path, next)) : Promise.resolve(null)),
    [token, report.reportId, JSON.stringify(query), JSON.stringify(path), next],
  );
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [path.length]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onPath([]); };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [onPath]);

  const first = result.data?.rows[0];
  const name = (step: DrillStep) => (first?.[step.slice] as DimensionValue | undefined)?.label ?? step.id ?? NOT_SET;
  const deeper = next && nextSlice(report.slices, [...used, next]);
  const pathSlices = new Set(path.map((s) => s.slice));
  const levelResult = result.data && { ...result.data, columns: result.data.columns.filter((c) => !pathSlices.has(c.key)) };

  return (
    <aside className="drill" aria-labelledby="drill-title">
      <div className="drill-head">
        <h2 id="drill-title" tabIndex={-1} ref={heading}>Детализация{next ? `: ${SLICE_TITLES[next] ?? next}` : ''}</h2>
        <button type="button" className="secondary" onClick={() => onPath([])}>Закрыть</button>
      </div>
      <nav aria-label="Уровни детализации" className="breadcrumbs">
        <button type="button" className="link-button" onClick={() => onPath([])}>Итог</button>
        {path.map((step, index) => (
          <span key={index}>
            {' › '}
            {index < path.length - 1
              ? <button type="button" className="link-button" onClick={() => onPath(path.slice(0, index + 1))}>{name(step)}</button>
              : <span aria-current="location">{SLICE_TITLES[step.slice] ?? step.slice}: {name(step)}</span>}
          </span>
        ))}
      </nav>
      {!next ? <Notice tone="info">Это последний уровень детализации.</Notice>
        : result.loading ? <Loading label="Загружаем уровень…" />
        : result.error ? (
          result.error instanceof ApiError && result.error.status === 403
            ? <Notice tone="warning">Детализация до уровня «{SLICE_TITLES[next] ?? next}» недоступна для вашей роли; показан только агрегат.</Notice>
            : <Failure message={errorMessage(result.error)} onRetry={result.reload} />
        )
        : !levelResult?.rows.length ? <Empty>На этом уровне данных нет.</Empty>
        : (
          <ResultTable
            result={levelResult}
            caption={`${report.reportId}: ${SLICE_TITLES[next] ?? next}`}
            drillLabel={deeper ? 'Детализировать' : undefined}
            onDrill={deeper ? (row) => onPath([...path, { slice: next, id: (row[next] as DimensionValue).id }]) : undefined}
          />
        )}
      {next === 'record' && <p className="muted">Исходные записи источника; открыть объект можно в системе-источнике по его идентификатору.</p>}
    </aside>
  );
}
