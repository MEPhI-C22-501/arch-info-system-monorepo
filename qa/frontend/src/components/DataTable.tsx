import { KeyboardEvent, MouseEvent, ReactNode } from 'react';
import { ErrorMessage } from './ErrorMessage';

export type Column<T> = { header: string; render: (row: T) => ReactNode };

type Selection = { selected: Set<string>; onChange: (selected: Set<string>) => void };

type Props<T> = {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  onOpen?: (row: T) => void;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyText: ReactNode;
  selection?: Selection;
  isSelectable?: (row: T) => boolean;
  isCurrent?: (row: T) => boolean;
};

const INTERACTIVE = 'a, button, input, select, textarea, label';

// Все списки устроены одинаково (110, раздел 1): строка открывается щелчком и по Enter.
export function DataTable<T>({ columns, rows, rowKey, onOpen, loading, error, onRetry, emptyText, selection, isSelectable = () => true, isCurrent }: Props<T>) {
  if (error && !rows) return <ErrorMessage error={error} onRetry={onRetry} />;

  const span = columns.length + (selection ? 1 : 0);
  const toggle = (key: string) => {
    if (!selection) return;
    const next = new Set(selection.selected);
    if (!next.delete(key)) next.add(key);
    selection.onChange(next);
  };
  const keys = (rows ?? []).filter(isSelectable).map(rowKey);
  const allSelected = keys.length > 0 && keys.every((key) => selection?.selected.has(key));
  const toggleAll = () => {
    if (!selection) return;
    const next = new Set(selection.selected);
    keys.forEach((key) => (allSelected ? next.delete(key) : next.add(key)));
    selection.onChange(next);
  };

  const open = (row: T) => (event: MouseEvent<HTMLTableRowElement>) => {
    if (!(event.target as Element).closest(INTERACTIVE)) onOpen?.(row);
  };
  const openByKey = (row: T) => (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' && event.target === event.currentTarget) onOpen?.(row);
  };

  return (
    <>
      {error ? <ErrorMessage error={error} onRetry={onRetry} /> : null}
      <table aria-busy={loading && !rows}>
        <thead>
          <tr>
            {selection && <th><input type="checkbox" aria-label="Выбрать все на странице" checked={allSelected} onChange={toggleAll} disabled={!keys.length} /></th>}
            {columns.map((column) => <th key={column.header}>{column.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {!rows && loading && [0, 1, 2, 3, 4].map((i) => (
            <tr key={i} data-testid="skeleton-row">{Array.from({ length: span }, (_, j) => <td key={j}><span className="skeleton" /></td>)}</tr>
          ))}
          {rows && rows.length === 0 && <tr><td colSpan={span}><div className="empty">{emptyText}</div></td></tr>}
          {rows?.map((row) => {
            const key = rowKey(row);
            const classes = [onOpen ? 'row' : '', isCurrent?.(row) ? 'current' : ''].join(' ').trim();
            return (
              <tr key={key} className={classes || undefined} tabIndex={onOpen ? 0 : undefined} onClick={open(row)} onKeyDown={openByKey(row)}>
                {selection && <td>{isSelectable(row) && <input type="checkbox" aria-label={`Выбрать ${key}`} checked={selection.selected.has(key)} onChange={() => toggle(key)} />}</td>}
                {columns.map((column) => <td key={column.header}>{column.render(row)}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
