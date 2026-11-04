import { useEffect, useId, useRef, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { Failure, Loading, Notice } from '../components/State';
import { dateTime, daysAgo, formatCell, sourceName, staleSources, today } from '../format';
import { useSession } from '../session';
import type { DimensionOption, Freshness, ReportQuery, ReportResult } from '../types';
import { useLoad, type Loaded } from '../useLoad';

export type Report = Loaded<ReportResult | null>;

/** One report request of a dashboard; null query means "not chosen yet" and asks nothing. */
export function useReport(reportId: string, query: ReportQuery | null): Report {
  const { token } = useSession();
  return useLoad(() => (query ? api<ReportResult>(token, `reports/${reportId}/query`, 'POST', query) : Promise.resolve(null)),
    [token, reportId, JSON.stringify(query)]);
}

/** Period and the chosen value live in the address, so a dashboard link can be shared. */
export function useDashboardParams(key: string) {
  const [search, setSearch] = useSearchParams();
  const from = search.get('from') ?? daysAgo(29);
  const to = search.get('to') ?? today();
  const value = search.get(key) ?? '';
  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(search);
    for (const [k, v] of Object.entries(changes)) if (v) next.set(k, v); else next.delete(k);
    setSearch(next, { replace: true });
  };
  return { from, to, value, set, valid: from <= to, param: (name: string) => search.get(name) ?? '' };
}

export function Tile({ title, value, note, delta }: { title: string; value: ReactNode; note?: ReactNode; delta?: number | null }) {
  return (
    <div className="total">
      <dt>{title}</dt>
      <dd>{value}</dd>
      {delta !== undefined && delta !== null && (
        <dd className="tile-delta">{delta > 0 ? '+' : ''}{formatCell(delta)} к прошлому периоду</dd>
      )}
      {note && <dd className="tile-note">{note}</dd>}
    </div>
  );
}

/**
 * Bars with the same numbers as a table under them (110: a chart is always duplicated by a table).
 * Without scale the longest bar takes the full width; with scale (e.g. the plan) a bar is a share of it.
 */
export function Bars({ title, points, unit = '', scale, note }: {
  title: string; points: { label: string; value: number | null }[]; unit?: string; scale?: number | null; note?: string;
}) {
  const id = useId();
  if (!points.length) return <p className="muted">{title}: данных нет.</p>;
  const max = Math.max(1, scale ?? 0, ...points.map((p) => Math.abs(p.value ?? 0)));
  const row = 32;
  return (
    <figure className="chart chart-compact">
      {note && <p className="muted chart-note">{note}</p>}
      <svg viewBox={`0 0 640 ${points.length * row + 8}`} role="img" aria-labelledby={id}>
        <title id={id}>{title}</title>
        {points.map((p, i) => (
          <g key={i}>
            <text x="0" y={i * row + 22} className="chart-label">{p.label.length > 28 ? p.label.slice(0, 27) + '…' : p.label}</text>
            {scale ? <rect x="220" y={i * row + 10} width="340" height="14" className="bar-track" /> : null}
            <rect x="220" y={i * row + 10} width={(Math.abs(p.value ?? 0) / max) * 340} height="14" className="bar" />
            <text x="630" y={i * row + 22} textAnchor="end" className="chart-value">{p.value === null ? '—' : formatCell(p.value) + unit}</text>
          </g>
        ))}
      </svg>
      <figcaption>
        <details>
          <summary>{title} — таблицей</summary>
          <table>
            <tbody>{points.map((p, i) => <tr key={i}><th scope="row">{p.label}</th><td className="num">{p.value === null ? '—' : formatCell(p.value) + unit}</td></tr>)}</tbody>
          </table>
        </details>
      </figcaption>
    </figure>
  );
}

/** "2,5 ч из 10 ч — 25 %": a filled share of a track; above 100 % the excess is marked. */
export function Progress({ title, value, max, unit }: { title: string; value: number | null; max: number | null; unit: string }) {
  const id = useId();
  if (value === null || !max || max <= 0) return <p className="muted">{title}: нет плана для сравнения.</p>;
  const share = value / max;
  const width = 600;
  return (
    <figure className="chart chart-compact progress">
      <figcaption id={id} className="progress-text">
        {title}: <strong>{formatCell(value)}{unit} из {formatCell(max)}{unit}</strong> — {formatCell(Math.round(share * 1000) / 10)} %
        {share > 1 && <span className="overrun"> (сверх плана на {formatCell(Math.round((value - max) * 100) / 100)}{unit})</span>}
      </figcaption>
      <svg viewBox={`0 0 ${width} 20`} role="img" aria-labelledby={id}>
        <rect x="0" y="2" width={width} height="16" rx="4" className="bar-track" />
        <rect x="0" y="2" width={Math.min(share, 1) * width} height="16" rx="4" className={share > 1 ? 'bar bar-negative' : 'bar'} />
      </svg>
    </figure>
  );
}

export type Tone = 'passed' | 'failed' | 'blocked' | 'skipped' | 'opened' | 'closed' | 'remaining';

function Swatch({ tone }: { tone: Tone }) {
  return <svg className="swatch" viewBox="0 0 12 12" aria-hidden="true"><rect width="12" height="12" rx="2" className={'tone-' + tone} /></svg>;
}

/** One bar = the whole (100 %), split into shares; the legend repeats every count and share, so colour is not the only sign. */
export function Stacked({ title, parts }: { title: string; parts: { label: string; value: number | null; tone: Tone }[] }) {
  const id = useId();
  const total = parts.reduce((s, p) => s + (p.value ?? 0), 0);
  if (!total) return <p className="muted">{title}: данных нет.</p>;
  const width = 600;
  let x = 0;
  const share = (v: number | null) => formatCell(Math.round(((v ?? 0) / total) * 1000) / 10);
  return (
    <figure className="chart chart-compact">
      <figcaption id={id} className="progress-text">{title}: всего {formatCell(total)}</figcaption>
      <svg viewBox={`0 0 ${width} 24`} role="img" aria-labelledby={id}>
        {parts.map((p) => {
          const w = ((p.value ?? 0) / total) * width;
          const rect = <rect key={p.label} x={x} y="2" width={w} height="20" className={'tone-' + p.tone} />;
          x += w;
          return rect;
        })}
      </svg>
      <ul className="legend">
        {parts.map((p) => <li key={p.label}><Swatch tone={p.tone} />{p.label} — {formatCell(p.value ?? 0)} ({share(p.value)} %)</li>)}
      </ul>
    </figure>
  );
}

/** Several measures per row on one scale (the largest value of the chart), with a legend and the same numbers as a table. */
export function GroupedBars({ title, series, rows }: {
  title: string; series: { key: string; label: string; tone: Tone }[]; rows: { label: string; values: Record<string, number | null> }[];
}) {
  const id = useId();
  if (!rows.length) return <p className="muted">{title}: данных нет.</p>;
  const max = Math.max(1, ...rows.flatMap((r) => series.map((s) => Math.abs(r.values[s.key] ?? 0))));
  const bar = 12;
  const group = series.length * (bar + 4) + 14;
  return (
    <figure className="chart chart-compact">
      <ul className="legend">{series.map((s) => <li key={s.key}><Swatch tone={s.tone} />{s.label}</li>)}</ul>
      <p className="muted chart-note">Длина полос — относительно наибольшего значения на графике ({formatCell(max)}).</p>
      <svg viewBox={`0 0 640 ${rows.length * group}`} role="img" aria-labelledby={id}>
        <title id={id}>{title}</title>
        {rows.map((r, i) => (
          <g key={r.label}>
            <text x="0" y={i * group + 14} className="chart-label">{r.label}</text>
            {series.map((s, j) => {
              const y = i * group + 4 + j * (bar + 4);
              const v = r.values[s.key];
              return (
                <g key={s.key}>
                  <rect x="160" y={y} width={(Math.abs(v ?? 0) / max) * 400} height={bar} className={'tone-' + s.tone} />
                  <text x="630" y={y + 10} textAnchor="end" className="chart-value">{v === null ? '—' : formatCell(v)}</text>
                </g>
              );
            })}
          </g>
        ))}
      </svg>
      <figcaption>
        <details>
          <summary>{title} — таблицей</summary>
          <table>
            <thead><tr><th scope="col">Неделя</th>{series.map((s) => <th key={s.key} scope="col" className="num">{s.label}</th>)}</tr></thead>
            <tbody>{rows.map((r) => <tr key={r.label}><th scope="row">{r.label}</th>{series.map((s) => <td key={s.key} className="num">{r.values[s.key] === null ? '—' : formatCell(r.values[s.key])}</td>)}</tr>)}</tbody>
          </table>
        </details>
      </figcaption>
    </figure>
  );
}

/** Single choice of a slice value from POST options (names within the user's scope). */
export function Choice({ reportId, slice, label, from, to, value, onChange, optional }: {
  reportId: string; slice: string; label: string; from: string; to: string; value: string; onChange: (id: string) => void; optional?: boolean;
}) {
  const { token } = useSession();
  const options = useLoad(() => (from <= to
    ? api<{ items: DimensionOption[] }>(token, `reports/${reportId}/options`, 'POST', { params: { periodFrom: from, periodTo: to }, slice: [slice] })
    : Promise.resolve({ items: [] })), [token, reportId, slice, from, to]);
  const items = options.data?.items ?? [];
  return (
    <label>{label}
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={options.loading && !options.data}>
        <option value="">{optional ? 'Все' : '— выберите —'}</option>
        {items.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
        {value && !items.some((o) => o.id === value) && <option value={value}>{value}</option>}
      </select>
      {options.error !== null && <span className="field-error">Список недоступен: {errorMessage(options.error)}</span>}
    </label>
  );
}

export function PeriodFields({ from, to, onChange }: { from: string; to: string; onChange: (changes: Record<string, string>) => void }) {
  const invalid = from > to;
  return (
    <>
      <label>С<input type="date" required value={from} onChange={(e) => onChange({ from: e.target.value })} aria-invalid={invalid} /></label>
      <label>По<input type="date" required value={to} onChange={(e) => onChange({ to: e.target.value })} aria-invalid={invalid} /></label>
      {invalid && <p className="field-error">Начало периода позже конца.</p>}
    </>
  );
}

/** Freshness of every source the dashboard used, and one warning per stale source. */
export function FreshnessLine({ reports }: { reports: Report[] }) {
  const seen = new Map<string, Freshness>();
  for (const r of reports) for (const f of r.data?.freshness ?? []) seen.set(f.source + f.stream, f);
  const all = [...seen.values()];
  if (!all.length) return null;
  return (
    <>
      <p className="freshness">{all.map((f) => `${sourceName(f.source)}: ${f.state === 'FRESH' ? 'актуально' : 'устарело'} на ${dateTime(f.dataAsOf)}`).join(' · ')}</p>
      {staleSources(all).map((text) => <Notice key={text} tone="warning">{text}. Показано последнее загруженное состояние.</Notice>)}
    </>
  );
}

/** Loading, error or the content of one dashboard block. */
export function Block({ report, children }: { report: Report; children: (data: ReportResult) => ReactNode }) {
  if (report.loading && !report.data) return <Loading />;
  if (report.error) return <Failure message={errorMessage(report.error)} onRetry={report.reload} />;
  return report.data ? <>{children(report.data)}</> : null;
}

/** SCR-04 refreshes itself once a minute without reloading the page. */
export function useAutoRefresh(reports: Report[], enabled: boolean) {
  const latest = useRef(reports);
  latest.current = reports;
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => latest.current.forEach((r) => r.reload()), 60000);
    return () => clearInterval(timer);
  }, [enabled]);
}

export const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);
