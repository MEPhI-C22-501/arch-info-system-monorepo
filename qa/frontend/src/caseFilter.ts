import type { CaseFilter } from './api/cases';
import type { Classifier } from './api/admin';
import type { FilterField } from './components/FilterBar';
import { CASE_STATUSES, MODULE_OPTIONS, statusLabel } from './labels';
import { optionsOf } from './useReferenceData';

// Поля отбора кейсов: одни и те же для списка, набора FILTER и добавления в план (050, CaseFilter).
export function caseFilterFields(classifiers: Classifier[] | undefined, statusEmptyLabel = 'Все, кроме архивных'): FilterField[] {
  return [
    { name: 'q', label: 'Поиск', type: 'text', placeholder: 'Ключ или название' },
    { name: 'module', label: 'Модуль', type: 'select', emptyLabel: 'Все модули', options: MODULE_OPTIONS },
    {
      name: 'status', label: 'Статус', type: 'select', emptyLabel: statusEmptyLabel,
      options: CASE_STATUSES.map((value) => ({ value, label: statusLabel(value) })),
    },
    { name: 'type', label: 'Тип', type: 'select', emptyLabel: 'Все типы', options: optionsOf(classifiers, 'CASE_TYPE') },
    { name: 'epicRef', label: 'Эпик', type: 'text' },
    {
      name: 'automated', label: 'Автоматизация', type: 'select', emptyLabel: 'Все',
      options: [{ value: 'true', label: 'Автотест' }, { value: 'false', label: 'Ручной' }],
    },
  ];
}

export function toCaseFilter(values: Record<string, string | undefined>): CaseFilter {
  const filter: CaseFilter = {};
  if (values.q) filter.q = values.q;
  if (values.module) filter.module = values.module;
  if (values.status) filter.status = values.status as CaseFilter['status'];
  if (values.type) filter.type = values.type;
  if (values.epicRef) filter.epicRef = values.epicRef;
  if (values.automated) filter.automated = values.automated === 'true';
  return filter;
}

const FILTER_LABELS: Record<string, string> = {
  q: 'поиск', module: 'модуль', status: 'статус', type: 'тип', epicRef: 'эпик', automated: 'автоматизирован', suiteId: 'состав набора',
};

// API отдаёт условие и с незаданными полями (null): они не показываются.
export function describeCaseFilter(filter: CaseFilter | null | undefined): string {
  const parts = Object.entries(filter ?? {})
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([name, value]) => (value === true ? FILTER_LABELS[name] : `${FILTER_LABELS[name] ?? name}: ${String(value)}`));
  return parts.join(', ') || '—';
}
