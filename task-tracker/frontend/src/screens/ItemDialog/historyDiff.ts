import { date, hours, typeName } from '../../api';
import type { Json } from '../../api';

export type HistoryEntry = {
  id: string;
  occurredAt: string;
  actorId?: string | null;
  externalSource?: string | null;
  relatedItems?: Record<string, string>;
  oldValues: unknown;
  newValues: unknown;
};

export type HistoryNames = {
  statuses: ReadonlyMap<string, string>;
  priorities: ReadonlyMap<string, string>;
  users: ReadonlyMap<string, string>;
  iterations: ReadonlyMap<string, string>;
  attachments: ReadonlyMap<string, string>;
  timeLogs: ReadonlyMap<string, string>;
};

const fieldLabels = {
  title: 'Название',
  description: 'Описание',
  type: 'Тип',
  statusId: 'Статус',
  priorityId: 'Приоритет',
  assigneeId: 'Исполнитель',
  startDate: 'Начало',
  dueDate: 'Срок',
  plannedHours: 'Плановая оценка',
  iterationId: 'Итерация',
  parentId: 'Родительский элемент',
  comment: 'Комментарий',
  severity: 'Серьёзность',
  environment: 'Окружение',
  testRunUrl: 'Ссылка на тестовый запуск',
  testCaseUrl: 'Ссылка на тест-кейс',
} as const;

type Field = keyof typeof fieldLabels;

const actionLabels = {
  childAdded: 'Прикреплён дочерний элемент',
  childRemoved: 'Откреплён дочерний элемент',
  linkAdded: 'Добавлена связь с другой задачей',
  linkRemoved: 'Удалена связь с другой задачей',
  commentAdded: 'Добавлен комментарий',
  commentRemoved: 'Удалён комментарий',
  attachmentAdded: 'Прикреплён файл',
  attachmentRemoved: 'Откреплён файл',
  timeLogAdded: 'Добавлена запись трудозатрат',
} as const;

export function readHistoryFields(value: unknown): Json {
  if (typeof value === 'string') {
    try { value = JSON.parse(value); } catch { return {}; }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const fields = value as Json;
  if ((fields.type === 'json' || fields.type === 'jsonb') && typeof fields.value === 'string') {
    return readHistoryFields(fields.value);
  }
  return fields;
}

const present = (value: unknown) => value !== null && value !== undefined && value !== '';
const lookup = (names: ReadonlyMap<string, string>, value: unknown) =>
  typeof value === 'string' ? names.get(value) : undefined;

function formatValue(field: Field, value: unknown, names: HistoryNames, relatedItems: ReadonlyMap<string, string>): string {
  if (!present(value)) return field === 'assigneeId' ? 'Не назначен' : '—';
  switch (field) {
    case 'statusId': return lookup(names.statuses, value) ?? 'Статус недоступен';
    case 'priorityId': return lookup(names.priorities, value) ?? 'Приоритет недоступен';
    case 'assigneeId': return lookup(names.users, value) ?? 'Пользователь недоступен';
    case 'iterationId': return lookup(names.iterations, value) ?? 'Итерация недоступна';
    case 'parentId': return lookup(relatedItems, value) ?? 'Карточка недоступна';
    case 'type': {
      const type = typeof value === 'string' ? typeName(value) : '';
      return type && type !== value ? type : 'Неизвестный тип';
    }
    case 'startDate':
    case 'dueDate':
      return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? date(value) : 'Дата недоступна';
    case 'plannedHours':
      return (typeof value === 'number' || typeof value === 'string') && Number.isFinite(Number(value))
        ? hours(value) : 'Оценка недоступна';
    case 'severity': {
      const labels = new Map([['critical', 'Критическая'], ['high', 'Высокая'], ['medium', 'Средняя'], ['low', 'Низкая']]);
      return lookup(labels, value) ?? 'Серьёзность недоступна';
    }
    default: return typeof value === 'string' ? value : 'Значение недоступно';
  }
}

export function describeHistoryEntry(entry: HistoryEntry, names: HistoryNames) {
  const before = readHistoryFields(entry.oldValues);
  const after = readHistoryFields(entry.newValues);
  const relatedItems = new Map(Object.entries(entry.relatedItems ?? {}));
  const changes = (Object.keys(fieldLabels) as Field[]).flatMap(field => {
    const oldValue = before[field], newValue = after[field];
    if (oldValue === newValue || (!present(oldValue) && !present(newValue))) return [];
    if (field === 'plannedHours' && present(oldValue) && present(newValue) && Number(oldValue) === Number(newValue)) return [];
    return [{ field, label: fieldLabels[field], before: formatValue(field, before[field], names, relatedItems),
      after: formatValue(field, after[field], names, relatedItems) }];
  });

  const actions = (Object.keys(actionLabels) as Array<keyof typeof actionLabels>).flatMap(key => {
    if (!after[key]) return [];
    let detail: string | undefined;
    if (key === 'childAdded' || key === 'childRemoved') detail = lookup(relatedItems, after[key]);
    if (key === 'linkAdded' || key === 'linkRemoved') {
      if (after.linkType === 'BLOCKS') detail = 'Зависимость «блокирует»';
      if (after.linkType === 'RELATED') detail = 'Связанные задачи';
    }
    if (key === 'timeLogAdded') detail = lookup(names.timeLogs, after[key]);
    if (key === 'attachmentAdded' || key === 'attachmentRemoved') {
      detail = typeof after.attachmentName === 'string' ? after.attachmentName : lookup(names.attachments, after[key]);
    }
    return [{ key, label: actionLabels[key], detail }];
  });

  const created = !present(before.type) && present(after.type) && !present(before.title) && present(after.title);
  const iterationChanged = changes.some(change => change.field === 'iterationId');
  const parentChanged = changes.some(change => change.field === 'parentId');
  let title = 'Изменена карточка';
  if (created) title = 'Карточка создана';
  else if (actions.length === 1 && changes.length === 0) title = actions[0].label;
  else if (iterationChanged) {
    title = !present(after.iterationId) ? 'Задача исключена из итерации'
      : present(before.iterationId) ? 'Задача перенесена в другую итерацию' : 'Задача добавлена в итерацию';
  } else if (parentChanged) {
    title = !present(after.parentId) ? 'Задача откреплена от родителя'
      : present(before.parentId) ? 'Изменён родительский элемент' : 'Задача прикреплена к родителю';
  } else if (changes.length === 1) {
    if (changes[0].field === 'statusId') title = 'Изменён статус';
    if (changes[0].field === 'assigneeId') title = 'Изменён исполнитель';
    if (changes[0].field === 'comment') title = 'Изменён комментарий';
  }

  const sources = new Map([['planning-system', 'Planning System'], ['qa', 'QA System'], ['qa-system', 'QA System'], ['excel', 'Импорт Excel']]);
  const actor = entry.actorId === 'system' ? 'Система'
    : entry.actorId ? names.users.get(entry.actorId) ?? 'Пользователь недоступен'
    : entry.externalSource ? sources.get(entry.externalSource.toLowerCase()) ?? 'Внешний сервис' : 'Система';

  const unrecognizedFields = [...Object.keys(before), ...Object.keys(after)]
    .some(key => !Object.hasOwn(fieldLabels, key) && !Object.hasOwn(actionLabels, key));
  return { actor, title, changes, actions, visible: changes.length > 0 || actions.length > 0 || unrecognizedFields };
}
