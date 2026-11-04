import { formatCell, label, numericValue } from '../format';
import type { Cell, Column, ReportResult } from '../types';

// M-04 is an overrun: shown in red with an explicit "+" (110, SCR-02), never by colour alone.
const OVERRUN = new Set(['M-04']);

function CellView({ column, value }: { column: Column; value: Cell | undefined }) {
  if (column.type === 'dimension') {
    const missing = !value || (typeof value === 'object' && 'id' in value && value.id === null);
    return <td className={missing ? 'not-set' : undefined}>{formatCell(value)}</td>;
  }
  const number = numericValue(value);
  if (OVERRUN.has(column.key) && typeof value === 'number' && value > 0) {
    return <td className="num overrun">+{formatCell(value)}<span className="visually-hidden"> (перерасход)</span></td>;
  }
  return <td className={number === null || typeof value === 'object' ? undefined : 'num'}>{formatCell(value)}</td>;
}

export function ResultTable({ result, caption }: { result: ReportResult; caption: string }) {
  const measures = result.columns.filter((c) => c.type === 'measure');
  const dimensions = result.columns.filter((c) => c.type === 'dimension');
  return (
    <div className="table-scroll" tabIndex={0} aria-label="Таблица результата, прокручивается по горизонтали">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {result.columns.map((column) => (
              <th key={column.key} scope="col" className={column.type === 'measure' ? 'num' : undefined}>
                {column.title}
                {column.formula && (
                  <span className="formula" title={column.formula} aria-label={'Формула: ' + column.formula} role="note"> ƒ</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, index) => (
            <tr key={index}>
              {result.columns.map((column) => <CellView key={column.key} column={column} value={row[column.key]} />)}
            </tr>
          ))}
        </tbody>
        {result.rows.length > 1 && (
          <tfoot>
            <tr>
              <th scope="row" colSpan={dimensions.length || 1}>Итого</th>
              {measures.map((column) => <CellView key={column.key} column={column} value={result.totals[column.key]} />)}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

export function Totals({ result }: { result: ReportResult }) {
  return (
    <dl className="totals">
      {Object.entries(result.totals).map(([key, value]) => (
        <div key={key} className="total">
          <dt>{result.columns.find((c) => c.key === key)?.title ?? label(key)}</dt>
          <dd>{formatCell(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
