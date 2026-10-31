import { screen, within } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import type { DefectStatus } from './api/defects';
import type { RunStatus } from './api/runs';
import { canArchiveSuite, canCommentDefect, canRecordResult, caseTransitions, defectTransitions, isCaseReadOnly, planActions, runActions } from './permissions';
import { DefectCard } from './screens/DefectCard';
import { RunCard } from './screens/RunCard';
import { CaseCard } from './screens/CaseCard';
import { CasesList } from './screens/CasesList';
import { SuitesList } from './screens/SuitesList';
import { ROLES, Role } from './session';
import { mockFetch, page, renderScreen } from './test/helpers';

describe('переходы дефекта (050, 070 раздел 4)', () => {
  const cases: [Role, DefectStatus, DefectStatus[]][] = [
    ['qa-lead', 'NEW', ['OPEN']],
    ['qa-tester', 'NEW', []],
    ['qa-automation', 'NEW', []],
    ['qa-viewer', 'NEW', []],
    ['qa-admin', 'NEW', []],
    ['qa-tester', 'FIXED', ['READY_FOR_TEST']],
    ['qa-tester', 'READY_FOR_TEST', ['CLOSED', 'REOPENED']],
    ['qa-tester', 'CLOSED', ['REOPENED']],
    ['qa-tester', 'REOPENED', []],
    ['qa-lead', 'REOPENED', ['IN_PROGRESS']],
    ['qa-lead', 'IN_PROGRESS', ['FIXED']],
    ['qa-automation', 'READY_FOR_TEST', []],
  ];
  test.each(cases)('%s в %s: %j', (role, status, expected) => {
    expect(defectTransitions(role, status)).toEqual(expected);
  });

  test('комментировать могут все, кроме администратора', () => {
    expect(ROLES.filter(canCommentDefect)).toEqual(['qa-lead', 'qa-tester', 'qa-automation', 'qa-viewer']);
  });
});

describe('кейс', () => {
  test('статус меняют редакторы, читатель и администратор — нет', () => {
    expect(caseTransitions('qa-tester', 'ACTUAL')).toEqual(['NEEDS_UPDATE', 'ARCHIVED']);
    expect(caseTransitions('qa-lead', 'ARCHIVED')).toEqual(['ACTUAL']);
    expect(caseTransitions('qa-viewer', 'ACTUAL')).toEqual([]);
    expect(caseTransitions('qa-admin', 'ACTUAL')).toEqual([]);
  });

  test('архивный кейс — только чтение', () => {
    expect(isCaseReadOnly('qa-lead', 'ARCHIVED')).toBe(true);
    expect(isCaseReadOnly('qa-lead', 'ACTUAL')).toBe(false);
    expect(isCaseReadOnly('qa-viewer', 'ACTUAL')).toBe(true);
  });
});

describe('прогон и план', () => {
  const cases: [Role, RunStatus, string[]][] = [
    ['qa-lead', 'CREATED', ['start', 'abort']],
    ['qa-lead', 'IN_PROGRESS', ['complete', 'abort']],
    ['qa-lead', 'COMPLETED', []],
    ['qa-lead', 'ABORTED', []],
    ['qa-tester', 'CREATED', ['start']],
    ['qa-tester', 'IN_PROGRESS', []],
    ['qa-automation', 'CREATED', ['start']],
    ['qa-viewer', 'CREATED', []],
    ['qa-admin', 'IN_PROGRESS', []],
  ];
  test.each(cases)('%s, прогон %s: %j', (role, status, expected) => {
    expect(runActions(role, status)).toEqual(expected);
  });

  test('результат: тестировщик — свой и неназначенный, лид — любой, только в выполняющемся', () => {
    const tester = { role: 'qa-tester', name: 'petrov' } as const;
    const lead = { role: 'qa-lead', name: 'ivanov' } as const;
    expect(canRecordResult(tester, 'IN_PROGRESS', { assignee: null })).toBe(true);
    expect(canRecordResult(tester, 'IN_PROGRESS', { assignee: 'petrov' })).toBe(true);
    expect(canRecordResult(tester, 'IN_PROGRESS', { assignee: 'sidorov' })).toBe(false);
    expect(canRecordResult(lead, 'IN_PROGRESS', { assignee: 'sidorov' })).toBe(true);
    expect(canRecordResult(lead, 'COMPLETED', { assignee: null })).toBe(false);
    expect(canRecordResult(lead, 'CREATED', { assignee: null })).toBe(false);
    expect(canRecordResult({ role: 'qa-automation', name: 'a' }, 'IN_PROGRESS', { assignee: null })).toBe(false);
    expect(canRecordResult({ role: 'qa-viewer', name: 'a' }, 'IN_PROGRESS', { assignee: null })).toBe(false);
  });

  test('план меняет только QA-лид и только открытый', () => {
    expect(planActions('qa-lead', 'DRAFT')).toEqual(['activate', 'cancel']);
    expect(planActions('qa-lead', 'ACTIVE')).toEqual(['complete', 'cancel']);
    expect(planActions('qa-lead', 'COMPLETED')).toEqual([]);
    expect(planActions('qa-tester', 'ACTIVE')).toEqual([]);
  });

  test('наборы «Smoke» и «Приёмка стенда» архивирует только лид, свой обычный — владелец', () => {
    const tester = { role: 'qa-tester', name: 'petrov' } as const;
    expect(canArchiveSuite(tester, { purpose: 'GENERAL', owner: 'petrov' })).toBe(true);
    expect(canArchiveSuite(tester, { purpose: 'GENERAL', owner: 'sidorov' })).toBe(false);
    expect(canArchiveSuite(tester, { purpose: 'SMOKE', owner: 'petrov' })).toBe(false);
    expect(canArchiveSuite({ role: 'qa-lead', name: 'x' }, { purpose: 'SMOKE', owner: 'y' })).toBe(true);
    expect(canArchiveSuite({ role: 'qa-viewer', name: 'y' }, { purpose: 'GENERAL', owner: 'y' })).toBe(false);
  });
});

const defect = {
  id: 'd1', key: 'DEF-02', origin: 'AUTO', title: '[TC-RM-03] провал', actualResult: 'факт', severity: 'MAJOR', priority: 'HIGH',
  status: 'NEW', author: 'ivanov', trackerSyncState: 'PENDING', trackerMismatch: false, reopenCount: 0,
  createdAt: '2026-10-30T10:00:00Z', updatedAt: '2026-10-30T10:00:00Z', runIds: ['r1'],
  runs: [{ runId: 'r1', runKey: 'RUN-02', resultId: 'res1', resultStatus: 'FAILED', linkedAt: '2026-10-30T10:00:00Z' }], comments: [],
};

function mockDefect(status: string) {
  return mockFetch(({ method, url }) => {
    if (method === 'GET' && url.endsWith('/defects/d1')) return { body: { ...defect, status } };
    if (url.endsWith('/defects/d1/history')) return { body: { items: [{ author: 'ivanov', source: 'SYSTEM', field: 'status', newValue: 'NEW', occurredAt: '2026-10-30T10:00:00Z' }] } };
    return undefined;
  });
}

describe('карточка дефекта по ролям', () => {
  test('лид видит допустимый переход и правку серьёзности', async () => {
    mockDefect('NEW');
    renderScreen(<DefectCard />, { role: 'qa-lead', path: '/defects/d1', pattern: '/defects/:id' });
    expect(await screen.findByRole('button', { name: '→ Открыт' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Закрыт/ })).toBeNull();
    expect(screen.getByLabelText('Серьёзность')).toBeTruthy();
    expect(await screen.findByText('SYSTEM')).toBeTruthy();
  });

  test('читатель видит «переходов нет», но может комментировать', async () => {
    mockDefect('READY_FOR_TEST');
    renderScreen(<DefectCard />, { role: 'qa-viewer', path: '/defects/d1', pattern: '/defects/:id' });
    expect(await screen.findByText('Для вашей роли переходов из этого статуса нет')).toBeTruthy();
    expect(screen.queryByLabelText('Серьёзность')).toBeNull();
    expect(screen.getByRole('button', { name: 'Добавить комментарий' })).toBeTruthy();
  });

  test('администратор не видит ни переходов, ни формы комментария', async () => {
    mockDefect('READY_FOR_TEST');
    renderScreen(<DefectCard />, { role: 'qa-admin', path: '/defects/d1', pattern: '/defects/:id' });
    expect(await screen.findByText('Для вашей роли переходов из этого статуса нет')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Добавить комментарий' })).toBeNull();
  });

  test('тестировщик переводит только статусы тестирования', async () => {
    mockDefect('READY_FOR_TEST');
    renderScreen(<DefectCard />, { role: 'qa-tester', path: '/defects/d1', pattern: '/defects/:id' });
    expect(await screen.findByRole('button', { name: '→ Закрыт' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '→ Переоткрыт' })).toBeTruthy();
  });
});

const run = {
  id: 'r1', key: 'RUN-02', environment: 'dev', trigger: 'MANUAL', startedBy: 'ivanov', createdAt: '2026-10-30T10:00:00Z',
  summary: { total: 1, passed: 0, failed: 0, blocked: 0, notRun: 1, skipped: 0, unverified: 0 }, smokeVerdict: null, verdict: null, planId: null, suiteId: null,
};
const result = { id: 'res1', testCaseId: 'c1', testCaseKey: 'TC-RM-03', title: 'Кейс', caseVersion: 2, status: 'NOT_RUN', assignee: null, steps: [], defect: null };

function mockRun(status: string) {
  return mockFetch(({ url }) => {
    if (url.endsWith('/runs/r1')) return { body: { ...run, status } };
    if (url.includes('/runs/r1/results')) return page([result]);
    return undefined;
  });
}

const runButtons = () => ['Запустить', 'Завершить', 'Прервать', 'Выполнить'].filter((name) => screen.queryByRole(name === 'Выполнить' ? 'link' : 'button', { name }));

describe('карточка прогона по ролям', () => {
  test.each<[Role, string, string[]]>([
    ['qa-lead', 'IN_PROGRESS', ['Завершить', 'Прервать', 'Выполнить']],
    ['qa-lead', 'CREATED', ['Запустить', 'Прервать']],
    ['qa-lead', 'COMPLETED', []],
    ['qa-tester', 'IN_PROGRESS', ['Выполнить']],
    ['qa-tester', 'CREATED', ['Запустить']],
    ['qa-automation', 'IN_PROGRESS', []],
    ['qa-viewer', 'IN_PROGRESS', []],
    ['qa-admin', 'IN_PROGRESS', []],
  ])('%s, прогон %s: %j', async (role, status, expected) => {
    mockRun(status);
    renderScreen(<RunCard />, { role, path: '/runs/r1', pattern: '/runs/:id' });
    await screen.findByText('TC-RM-03');
    expect(runButtons()).toEqual(expected);
  });

  test('завершённый прогон объявляет режим чтения', async () => {
    mockRun('COMPLETED');
    renderScreen(<RunCard />, { path: '/runs/r1', pattern: '/runs/:id' });
    expect(await screen.findByText('Прогон закрыт: результаты только для чтения.')).toBeTruthy();
  });
});

const testCase = {
  id: 'c1', key: 'TC-RM-03', status: 'ACTUAL', version: 1, currentVersion: 1, module: 'RM', title: 'Кейс', description: null, preconditions: null,
  priority: 'HIGH', severity: 'MAJOR', type: 'FUNCTIONAL', automated: false, autotestKey: null, featureRef: null, epicRef: null, requirementRef: null,
  templateId: null, copiedFromId: null, createdBy: 'seed', createdAt: '2026-10-30T10:00:00Z', updatedAt: '2026-10-30T10:00:00Z',
  steps: [{ id: 's1', position: 1, action: 'Шаг', expectedResult: 'Итог' }], lastResult: null,
};

function mockCase(status = 'ACTUAL') {
  return mockFetch(({ url }) => {
    if (url.includes('/admin/classifiers')) return page([]);
    if (url.endsWith('/test-cases/c1/versions')) return { body: { items: [{ version: 1, author: 'seed', createdAt: '2026-10-30T10:00:00Z', changedFields: [] }] } };
    if (url.includes('/test-cases/c1')) return { body: { ...testCase, status } };
    return undefined;
  });
}

describe('карточка кейса по ролям', () => {
  test('читатель не видит кнопок изменения', async () => {
    mockCase();
    renderScreen(<CaseCard />, { role: 'qa-viewer', path: '/test-cases/c1', pattern: '/test-cases/:id' });
    await screen.findByText('История версий');
    for (const name of ['Сохранить версию', 'В архив', 'На доработку', 'Копировать', 'Добавить шаг']) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
    expect((screen.getByLabelText('Название') as HTMLInputElement).disabled).toBe(true);
  });

  test('редактор видит сохранение и переходы текущего статуса', async () => {
    mockCase();
    renderScreen(<CaseCard />, { role: 'qa-tester', path: '/test-cases/c1', pattern: '/test-cases/:id' });
    expect(await screen.findByRole('button', { name: 'Сохранить версию' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'На доработку' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'В архив' })).toBeTruthy();
    expect((screen.getByLabelText('Ключ автотеста') as HTMLInputElement).disabled).toBe(true);
  });

  test('архивный кейс: только чтение с предложением вернуть в работу', async () => {
    mockCase('ARCHIVED');
    renderScreen(<CaseCard />, { role: 'qa-lead', path: '/test-cases/c1', pattern: '/test-cases/:id' });
    expect(await screen.findByRole('button', { name: 'Вернуть в работу' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Сохранить версию' })).toBeNull();
    expect((screen.getByLabelText('Название') as HTMLInputElement).disabled).toBe(true);
  });
});

describe('списки по ролям', () => {
  test('читатель не видит создания и выбора кейсов', async () => {
    mockFetch(({ url }) => {
      if (url.includes('/admin/classifiers')) return page([]);
      if (url.includes('/test-cases')) return page([testCase]);
      return undefined;
    });
    renderScreen(<CasesList />, { role: 'qa-viewer' });
    await screen.findByText('TC-RM-03');
    expect(screen.queryByRole('link', { name: 'Создать кейс' })).toBeNull();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  test('«Smoke» с нулём кейсов объясняет причину, архив и прогон — по праву', async () => {
    mockFetch(({ url }) => {
      if (url.includes('/suites')) {
        return page([{ id: 's1', name: 'Smoke', kind: 'FILTER', purpose: 'SMOKE', status: 'ACTIVE', owner: 'demo-seed', caseIds: [], caseCount: 0, filter: { automated: true } }]);
      }
      return undefined;
    });
    renderScreen(<SuitesList />, { role: 'qa-tester', name: 'petrov' });
    const row = (await screen.findByText(/автотестов пока нет/)).closest('tr')!;
    expect(within(row).getByText('0')).toBeTruthy();
    expect(within(row).getByRole('link', { name: 'Создать прогон' })).toBeTruthy();
    expect(within(row).queryByRole('button', { name: 'В архив' })).toBeNull();
  });
});
