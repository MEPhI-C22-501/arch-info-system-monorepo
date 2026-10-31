import type { Role } from './session';

export const ROLE_LABELS: Record<Role, string> = {
  'qa-lead': 'QA-лид',
  'qa-tester': 'Тестировщик',
  'qa-automation': 'Автоматизатор',
  'qa-viewer': 'Разработчик / РП',
  'qa-admin': 'Администратор',
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Черновик',
  ACTUAL: 'Актуален',
  NEEDS_UPDATE: 'На доработке',
  ARCHIVED: 'В архиве',
  ACTIVE: 'Активен',
  COMPLETED: 'Завершён',
  CANCELLED: 'Отменён',
  CREATED: 'Создан',
  IN_PROGRESS: 'Выполняется',
  ABORTED: 'Прерван',
  NOT_RUN: 'Не выполнен',
  PASSED: 'Пройден',
  FAILED: 'Провален',
  BLOCKED: 'Заблокирован',
  SKIPPED: 'Пропущен',
  NEW: 'Новый',
  OPEN: 'Открыт',
  FIXED: 'Исправлен',
  READY_FOR_TEST: 'Готов к проверке',
  CLOSED: 'Закрыт',
  REOPENED: 'Переоткрыт',
  ACCEPTED: 'Принято',
  REJECTED: 'Отклонено',
};
// Один код статуса у дефекта значит не то же, что у прогона.
const DEFECT_LABELS: Record<string, string> = { IN_PROGRESS: 'В работе' };

export type StatusKind = 'default' | 'defect';

export function statusLabel(status: string, kind: StatusKind = 'default'): string {
  return (kind === 'defect' && DEFECT_LABELS[status]) || STATUS_LABELS[status] || status;
}

export const CASE_STATUSES = ['DRAFT', 'ACTUAL', 'NEEDS_UPDATE', 'ARCHIVED'] as const;
export const PLAN_STATUSES = ['DRAFT', 'ACTIVE', 'COMPLETED', 'CANCELLED'] as const;
export const RUN_STATUSES = ['CREATED', 'IN_PROGRESS', 'COMPLETED', 'ABORTED'] as const;
export const RESULT_STATUSES = ['NOT_RUN', 'PASSED', 'FAILED', 'BLOCKED', 'SKIPPED'] as const;
export const DEFECT_STATUSES = ['NEW', 'OPEN', 'IN_PROGRESS', 'FIXED', 'READY_FOR_TEST', 'CLOSED', 'REOPENED'] as const;
export const SEVERITIES = ['BLOCKER', 'CRITICAL', 'MAJOR', 'MINOR', 'TRIVIAL'] as const;
// Списка модулей в API нет: подсистемы стартового набора (vision 7), сервер проверяет те же коды.
export const MODULE_OPTIONS = [
  { value: 'RM', label: 'RM — Reference Manager' },
  { value: 'TT', label: 'TT — Task Tracker' },
  { value: 'PS', label: 'PS — Planning System' },
  { value: 'REP', label: 'REP — Reports' },
  { value: 'INF', label: 'INF — Infra' },
];

export const PURPOSE_LABELS: Record<string, string> = { GENERAL: 'Общий', SMOKE: 'Smoke', ACCEPTANCE: 'Приёмка стенда' };
export const KIND_LABELS: Record<string, string> = { MANUAL: 'Ручной', FILTER: 'По фильтру' };
export const SCOPE_LABELS: Record<string, string> = { RELEASE: 'Релиз', ITERATION: 'Итерация', PROJECT: 'Проект', MODULE: 'Модуль' };

export function formatDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—';
}
