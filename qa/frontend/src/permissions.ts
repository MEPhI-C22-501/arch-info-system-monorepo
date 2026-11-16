import type { Suite } from './api/suites';
import type { Run, RunResult, RunStatus, RunAction } from './api/runs';
import type { TestCase, TestCaseStatus } from './api/cases';
import type { DefectStatus } from './api/defects';
import type { PlanAction, TestPlanStatus } from './api/plans';
import { hasRole, sessionRoles, sessionSubject } from './session';
import type { Role, RoleSelection, Session } from './session';

// Кнопки показываются по 070 и 050; сервер всё равно проверяет каждое действие (FR-SEC-01).
const CASE_EDITORS: Role[] = ['qa-tester', 'qa-automation', 'qa-lead'];

export const canEditCase = (role: RoleSelection) => hasRole(role, ...CASE_EDITORS);
export const canEditAutotest = (role: RoleSelection) => hasRole(role, 'qa-automation', 'qa-lead');
export const canManageSuites = canEditCase;
export const canManagePlans = (role: RoleSelection) => hasRole(role, 'qa-lead');
export const canCreateRun = canEditCase;
export const canEditDefect = canEditCase;
export const canCommentDefect = (role: RoleSelection) => hasRole(role, 'qa-viewer', ...CASE_EDITORS);
export const canAdminister = (role: RoleSelection) => hasRole(role, 'qa-admin');

const CASE_TRANSITIONS: Record<TestCaseStatus, TestCaseStatus[]> = {
  DRAFT: ['ACTUAL'],
  ACTUAL: ['NEEDS_UPDATE', 'ARCHIVED'],
  NEEDS_UPDATE: ['ACTUAL', 'ARCHIVED'],
  ARCHIVED: ['ACTUAL'],
};

export function caseTransitions(role: RoleSelection, status: TestCaseStatus): TestCaseStatus[] {
  return canEditCase(role) ? CASE_TRANSITIONS[status] : [];
}

// Только черновик: свой, QA-лид — любой (070, раздел 2); кейс с прогонами отклонит сервер.
export function canDeleteCase(session: Session, testCase: Pick<TestCase, 'status' | 'createdBy'>): boolean {
  if (testCase.status !== 'DRAFT') return false;
  return hasRole(sessionRoles(session), 'qa-lead') || (canEditCase(sessionRoles(session)) && testCase.createdBy === sessionSubject(session));
}

export function isCaseReadOnly(role: RoleSelection, status: TestCaseStatus): boolean {
  return !canEditCase(role) || status === 'ARCHIVED';
}

// «Smoke» и «Приёмка стенда» архивирует QA-лид, остальные наборы — ещё и владелец.
export function canArchiveSuite(session: Session, suite: Pick<Suite, 'purpose' | 'owner'>): boolean {
  if (hasRole(sessionRoles(session), 'qa-lead')) return true;
  return canManageSuites(sessionRoles(session)) && suite.purpose === 'GENERAL' && suite.owner === sessionSubject(session);
}

const PLAN_ACTIONS: Record<TestPlanStatus, PlanAction[]> = {
  DRAFT: ['activate', 'cancel'],
  ACTIVE: ['complete', 'cancel'],
  COMPLETED: [],
  CANCELLED: [],
};

export function planActions(role: RoleSelection, status: TestPlanStatus): PlanAction[] {
  return canManagePlans(role) ? PLAN_ACTIONS[status] : [];
}

export function isPlanOpen(status: TestPlanStatus): boolean {
  return status === 'DRAFT' || status === 'ACTIVE';
}

export function runActions(role: RoleSelection, status: RunStatus): RunAction[] {
  const actions: RunAction[] = [];
  if (status === 'CREATED' && canCreateRun(role)) actions.push('start');
  if (hasRole(role, 'qa-lead')) {
    if (status === 'IN_PROGRESS') actions.push('complete');
    if (status === 'CREATED' || status === 'IN_PROGRESS') actions.push('abort');
  }
  return actions;
}

// Только прогон без записанных результатов (120, раздел 8); остальное отклонит сервер.
export const canDeleteRuns = (role: RoleSelection) => hasRole(role, 'qa-lead');

export function canDeleteRun(role: RoleSelection, run: Pick<Run, 'summary'>): boolean {
  return canDeleteRuns(role) && run.summary.notRun === run.summary.total;
}

export function canRecordResult(session: Session, runStatus: RunStatus, result: Pick<RunResult, 'assignee'>): boolean {
  if (runStatus !== 'IN_PROGRESS') return false;
  if (hasRole(sessionRoles(session), 'qa-lead')) return true;
  return hasRole(sessionRoles(session), 'qa-tester') && (!result.assignee || result.assignee === sessionSubject(session));
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

export function defectTransitions(role: RoleSelection, status: DefectStatus): DefectStatus[] {
  return DEFECT_TRANSITIONS[status].filter((target) =>
    DEVELOPMENT_STATUSES.includes(target) ? hasRole(role, 'qa-lead') : hasRole(role, 'qa-lead', 'qa-tester'),
  );
}
