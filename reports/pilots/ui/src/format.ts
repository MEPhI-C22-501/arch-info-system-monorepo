import type { Cell, Freshness, ReportQuery } from './types';

export const NOT_SET = 'не задано';

export const SLICE_TITLES: Record<string, string> = {
  project: 'Проект', unit: 'Подразделение', role: 'Проектная роль', employee: 'Сотрудник', iteration: 'Итерация',
  epic: 'Эпик', week: 'Неделя', month: 'Месяц', record: 'Запись', grade: 'Грейд', status: 'Статус', type: 'Вид задачи', severity: 'Серьёзность',
};

/** Query parameters in words: the empty result (SCR-02) and the export list (SCR-08). */
export function describeQuery(query: ReportQuery): string {
  const params = query.params;
  const filters = [['проекты', params.projectIds], ['итерации', params.iterationIds], ['сотрудники', params.employeeIds]] as const;
  return [`период ${params.periodFrom} — ${params.periodTo}`, `разрез «${query.slice.map((s) => SLICE_TITLES[s] ?? s).join(' › ')}»`,
    ...filters.filter(([, ids]) => ids?.length).map(([name, ids]) => `${name}: выбрано ${ids!.length}`)].join(', ');
}

const LABELS: Record<string, string> = {
  opened: 'Создано', closed: 'Закрыто', remaining: 'Остаток', cycleMedian: 'Цикл, медиана', cycleP85: 'Цикл, p85',
  leadMedian: 'Полный срок, медиана', leadP85: 'Полный срок, p85', throughput: 'Завершено по неделям',
  averageWip: 'Среднее задач в работе', errorPercent: 'Отклонение, %', correctionCoefficient: 'Коэффициент',
  eligibleTasks: 'Задач с оценкой', quality: 'Качество', crossCheckFinish: 'Сверочный прогноз',
  missingInputs: 'Недостающие данные', estimatedTotalCost: 'Прогноз стоимости', currencyCode: 'Валюта',
  taskCount: 'Задач', demandHours: 'Потребность, ч', allocatedHours: 'Назначено, ч', availableHours: 'Доступно, ч',
  overdueDays: 'Дней просрочки', missingDueDates: 'Без срока', lateCompletedDays: 'Дней опоздания',
  passed: 'Успешно', failed: 'С ошибкой', blocked: 'Заблокировано', skipped: 'Пропущено',
  candidateDefectDensity: 'Плотность дефектов (кандидат)',
};

const NOTES: Record<string, string> = {
  PERIOD_NOT_FINISHED: 'Период ещё не завершён: показаны данные, известные на время обновления.',
  PARTIAL_PLANNING_FORECAST: 'Прогноз неполный: часть исходных данных отсутствует.',
  NO_DATA: 'По заданным параметрам данных нет.',
  'Q-REP-12_DENSITY_NOT_APPROVED': 'Методика плотности дефектов ещё не согласована.',
  INCOMPLETE_DEFECT_TIMELINE: 'История дефектов неполная.',
  INCOMPLETE_TASK_HISTORY: 'История задач неполная.',
  MISSING_CAPACITY: 'Нет полной информации о доступных часах.',
  PARTIAL_PLANNING_PERIOD_NOT_PRORATED: 'Плановый интервал загружен не полностью: часы не распределяются произвольно.',
  MISSING_WORKING_STATUS_MAPPING_OR_HISTORY: 'Для времени цикла нужны история и соответствие рабочих статусов.',
  MISSING_PLANNING_FORECAST: 'Прогноз планирования не загружен.',
  LABOR_MEASURES_REDACTED: 'Трудозатраты скрыты для вашей роли.',
};

const SOURCES: Record<string, string> = {
  'task-tracker': 'Трекер задач', 'planning-system': 'Планирование', 'reference-manager': 'Справочники', 'qa-system': 'Тестирование',
};

const NUMBER = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
const DATE_TIME = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Moscow' });

export function label(key: string): string {
  return LABELS[key] ?? key;
}

export function formatCell(value: Cell | undefined): string {
  if (value === null || value === undefined) return NOT_SET;
  if (typeof value === 'number') return NUMBER.format(value);
  if (typeof value === 'string') return value === 'PARTIAL' ? 'Неполные данные' : value === 'COMPLETE' ? 'Полные данные' : value === 'RATE' ? 'Ставка' : value;
  if (Array.isArray(value)) return value.map((v) => formatCell(v as Cell)).join(', ');
  if ('label' in value && typeof value.label === 'string') return value.label;
  return Object.entries(value).map(([k, v]) => `${label(k)}: ${formatCell(v as Cell)}`).join('; ');
}

export function noteText(code: string): string {
  if (code.startsWith('MISSING_MAPPING:')) return 'Не подтверждено соответствие идентификаторов.';
  return NOTES[code] ?? 'Не хватает исходных данных для части показателей.';
}

export function sourceName(source: string): string {
  return SOURCES[source] ?? source;
}

export function dateTime(value: string | null | undefined): string {
  return value ? DATE_TIME.format(new Date(value)) + ' МСК' : NOT_SET;
}

/** Lag in the largest whole unit: "45 с", "12 мин", "2 ч". */
export function duration(seconds: number | null): string {
  if (seconds === null) return 'нет данных';
  if (seconds < 120) return `${seconds} с`;
  if (seconds < 7200) return `${Math.round(seconds / 60)} мин`;
  return `${Math.round(seconds / 3600)} ч`;
}

/** The warning lines of SCR-02: "Данные источника «Трекер задач» актуальны на 05.10.2026, 10:00 МСК, задержка 2 ч". */
export function staleSources(freshness: Freshness[]): string[] {
  return freshness.filter((f) => f.state !== 'FRESH').map((f) => f.dataAsOf
    ? `Данные источника «${sourceName(f.source)}» актуальны на ${dateTime(f.dataAsOf)}, задержка ${duration(f.lagSeconds)}`
    : `Данные источника «${sourceName(f.source)}» ещё не загружены`);
}

/** First numeric value inside a cell: plain numbers or the first number nested in an object. */
export function numericValue(value: Cell | undefined): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (value && typeof value === 'object' && !Array.isArray(value) && !('label' in value)) {
    for (const nested of Object.values(value)) {
      const found = numericValue(nested as Cell);
      if (found !== null) return found;
    }
  }
  return null;
}

export function today(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(new Date());
}

/** The date n days before today in Moscow: dashboards default to the last 30 days. */
export function daysAgo(n: number): string {
  const day = new Date(today() + 'T00:00:00Z');
  day.setUTCDate(day.getUTCDate() - n);
  return day.toISOString().slice(0, 10);
}

/** Monday of the current week in Moscow: the default period (110, section 1). */
export function weekStart(): string {
  const day = new Date(today() + 'T00:00:00Z');
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}
