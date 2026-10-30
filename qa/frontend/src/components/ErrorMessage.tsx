import { ApiError, ErrorItem } from '../api/client';

const PLACE_LABELS: Record<string, string> = { case: 'кейс', template: 'шаблон', defect: 'дефект', run: 'прогон', schedule: 'расписание' };

// Причины сервера (130, раздел 5) в виде, понятном человеку; неизвестные показываются как есть.
export function formatErrorItem({ field, reason = '' }: ErrorItem): string {
  const usedBy = reason.match(/^used-by:([a-z]+):(.+)$/);
  if (usedBy) return `${PLACE_LABELS[usedBy[1]] ?? usedBy[1]} ${usedBy[2]}`;
  const prefixed = reason.match(/^(allowed|open-auto|unfinished|running|current):(.*)$/);
  if (prefixed) {
    const [, kind, value] = prefixed;
    if (kind === 'allowed') return `допустимо: ${value.split(',').join(', ')}`;
    if (kind === 'open-auto') return `незакрытый автодефект ${value}`;
    if (kind === 'unfinished') return `не завершён ${value}`;
    if (kind === 'running') return `выполняется ${value}`;
    return `текущая версия ${value}`;
  }
  const text = reason === 'required' ? 'обязательное поле' : reason;
  return field && field !== 'filter' ? `${field}: ${text}` : text;
}

export function ErrorMessage({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const api = error instanceof ApiError ? error : null;
  return (
    <div className="error" role="alert">
      {api ? <><code>{api.code}</code>: {api.message}</> : 'Не удалось выполнить запрос'}
      {api && api.errors.length > 0 && (
        <ul>{api.errors.map((item, i) => <li key={i}>{formatErrorItem(item)}</li>)}</ul>
      )}
      {onRetry && <div style={{ marginTop: 6 }}><button type="button" onClick={onRetry}>Повторить</button></div>}
    </div>
  );
}
