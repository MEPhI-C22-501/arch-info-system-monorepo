import { formatCell, numericValue } from '../format';
import type { ReportResult } from '../types';

const ROW = 44;
const MAX_ROWS = 12;

/** Horizontal bars for the first numeric measure; the table always carries the same data (110: charts are duplicated by a table). */
export function BarChart({ result }: { result: ReportResult }) {
  const measure = result.columns.find((c) => c.type === 'measure' && result.rows.some((r) => numericValue(r[c.key]) !== null));
  const dimension = result.columns.find((c) => c.type === 'dimension');
  if (!measure || !dimension || !result.rows.length) return <p className="muted">Нет числового показателя для графика.</p>;
  const rows = result.rows.slice(0, MAX_ROWS).map((row) => ({ name: formatCell(row[dimension.key]), value: numericValue(row[measure.key]) ?? 0 }));
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.value)));
  const height = rows.length * ROW + 16;
  return (
    <figure className="chart">
      <svg viewBox={`0 0 640 ${height}`} role="img" aria-labelledby="chart-title">
        <title id="chart-title">{measure.title} по разрезу «{dimension.title}»</title>
        {rows.map((row, index) => {
          const width = (Math.abs(row.value) / max) * 300;
          const y = index * ROW + 8;
          return (
            <g key={index}>
              <text x="0" y={y + 14} className="chart-label">{row.name.length > 40 ? row.name.slice(0, 39) + '…' : row.name}</text>
              <rect x={row.value < 0 ? 300 - width : 300} y={y + 20} width={width} height="12" className={row.value < 0 ? 'bar bar-negative' : 'bar'} />
              <text x="630" y={y + 31} textAnchor="end" className="chart-value">{formatCell(row.value)}</text>
            </g>
          );
        })}
      </svg>
      {result.rows.length > MAX_ROWS && <figcaption className="muted">Показаны первые {MAX_ROWS} строк из {result.rows.length}; полный список — в таблице.</figcaption>}
    </figure>
  );
}
