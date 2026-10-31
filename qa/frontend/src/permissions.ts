import type { Suite } from './api/suites';
import type { Run, RunResult, RunStatus, RunAction } from './api/runs';
import type { TestCase, TestCaseStatus } from './api/cases';
import type { DefectStatus } from './api/defects';
import type { PlanAction, TestPlanStatus } from './api/plans';
import type { Role, Session } from './session';

// Кнопки показываются по 070 и 050; сервер всё равно проверяет каждое действие (FR-SEC-01).
const CASE_EDITORS: Role[] = ['qa-tester', 'qa-automation', 'qa-lead'];

export const canEditCase = (role: Role) => CASE_EDITORS.includes(role);
export const canEditAutotest = (role: Role) => role === 'qa-automation' || role === 'qa-lead';
export const canManageSuites = canEditCase;
export const canManagePlans = (role: Role) => role === 'qa-lead';
export const canCreateRun = canEditCase;
export const canEditDefect = canEditCase;
export const canCommentDefect = (role: Role) => role !== 'qa-admin';
export const canAdminister = (role: Role) => role === 'qa-admin';

const CASE_TRANSITIONS: Record<TestCaseStatus, TestCaseStatus[]> = {
  DRAFT: ['ACTUAL'],
  ACTUAL: ['NEEDS_UPDATE', 'ARCHIVED'],
  NEEDS_UPDATE: ['ACTUAL', 'ARCHIVED'],
  ARCHIVED: ['ACTUAL'],
};

export function caseTransitions(role: Role, status: TestCaseStatus): TestCaseStatus[] {
  return canEditCase(role) ? CASE_TRANSITIONS[status] : [];
}

// Только черновик: свой, QA-лид — любой (070, раздел 2); кейс с прогонами отклонит сервер.
export function canDeleteCase(session: Session, testCase: Pick<TestCase, 'status' | 'createdBy'>): boolean {
  if (testCase.status !== 'DRAFT') return false;
  return session.role === 'qa-lead' || (canEditCase(session.role) && testCase.createdBy === session.name);
}

export function isCaseReadOnly(role: Role, status: TestCaseStatus): boolean {
  return !canEditCase(role) || status === 'ARCHIVED';
}

// «Smoke» и «Приёмка стенда» архивирует QA-лид, остальные наборы — ещё и владелец.
export function canArchiveSuite(session: Session, suite: Pick<Suite, 'purpose' | 'owner'>): boolean {
  if (session.role === 'qa-lead') return true;
  return canManageSuites(session.role) && suite.purpose === 'GENERAL' && suite.owner === session.name;
}

const PLAN_ACTIONS: Record<TestPlanStatus, PlanAction[]> = {
  DRAFT: ['activate', 'cancel'],
  ACTIVE: ['complete', 'cancel'],
  COMPLETED: [],
  CANCELLED: [],
};

export function planActions(role: Role, status: TestPlanStatus): PlanAction[] {
  return canManagePlans(role) ? PLAN_ACTIONS[status] : [];
}

export function isPlanOpen(status: TestPlanStatus): boolean {
  return status === 'DRAFT' || status === 'ACTIVE';
}

export function runActions(role: Role, status: RunStatus): RunAction[] {
  const actions: RunAction[] = [];
  if (status === 'CREATED' && canCreateRun(role)) actions.push('start');
  if (role === 'qa-lead') {
    if (status === 'IN_PROGRESS') actions.push('complete');
    if (status === 'CREATED' || status === 'IN_PROGRESS') actions.push('abort');
  }
  return actions;
}

// Только прогон без записанных результатов (120, раздел 8); остальное отклонит сервер.
export const canDeleteRuns = (role: Role) => role === 'qa-lead';

export function canDeleteRun(role: Role, run: Pick<Run, 'summary'>): boolean {
  return canDeleteRuns(role) && run.summary.notRun === run.summary.total;
}

export function canRecordResult(session: Session, runStatus: RunStatus, result: Pick<RunResult, 'assignee'>): boolean {
  if (runStatus !== 'IN_PROGRESS') return false;
  if (session.role === 'qa-lead') return true;
  return session.role === 'qa-tester' && (!result.assignee || result.assignee === session.name);
}

const DEFECT_TRANSITIONS: Record<DefectStatus, DefectStatus[]> = {
  NEW: ['OPEN'],
  OPEN: ['IN_PROGRESS'],
  IN_PROGRESS: ['FIXED'],
  FIXED: ['READY_FOR_TEST'],
  READY_FOR_TEST: ['CLOSED', 'REOPENED'],
  CLOSED: ['REOPENED'],
  REOPENED: ['IN_PROGRESS'],
};
const DEVELOPMENT_STATUSES: DefectStatus[] = ['OPEN', 'IN_PROGRESS', 'FIXED'];

export function defectTransitions(role: Role, status: DefectStatus): DefectStatus[] {
  return DEFECT_TRANSITIONS[status].filter((target) =>
    DEVELOPMENT_STATUSES.includes(target) ? role === 'qa-lead' : role === 'qa-lead' || role === 'qa-tester',
  );
}
