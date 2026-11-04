// Calls the Reports API with the in-memory token. The server decides access on every request;
// the UI only hides what a role cannot use.

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly correlationId?: string) {
    super(`${status}: ${code}`);
  }
}

let onUnauthorized: () => void = () => undefined;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export async function api<T>(token: string, path: string, method = 'GET', body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  const response = await fetch('/api/v1/' + path, {
    method,
    cache: 'no-store',
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) onUnauthorized();
    let payload: { code?: string; correlationId?: string } = {};
    try { payload = await response.json(); } catch { payload = { code: 'REQUEST_FAILED' }; }
    throw new ApiError(response.status, payload.code ?? 'REQUEST_FAILED', payload.correlationId);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get('Content-Type') ?? '';
  return (type.includes('json') ? await response.json() : await response.blob()) as T;
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : 'Неизвестная ошибка';
  const texts: Record<number, string> = {
    400: 'Запрос отклонён сервером.',
    401: 'Сеанс истёк. Войдите снова.',
    403: 'Нет доступа к этим данным для вашей роли.',
    404: 'Не найдено.',
    409: 'Данные изменились. Обновите страницу и повторите.',
    422: 'Проверьте параметры запроса.',
    503: 'Источник данных ещё не загружен. Повторите позже.',
  };
  const text = texts[error.status] ?? 'Сервис недоступен. Повторите позже.';
  return error.correlationId ? `${text} Код обращения: ${error.correlationId}.` : text;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
