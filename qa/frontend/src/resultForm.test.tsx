import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import type { Run, RunResult } from './api/runs';
import { defectMessage, deriveStatus, finalStatus, resultFormOf, toResultInput, validateResult } from './resultForm';
import { ResultForm } from './screens/ExecuteCase';
import { mockFetch, renderScreen } from './test/helpers';

const result = {
  id: 'res1', testCaseId: 'c1', testCaseKey: 'TC-RM-03', title: 'Кейс', caseVersion: 2, status: 'NOT_RUN', assignee: null, actualResult: null,
  comment: null, failureReason: null, defect: null,
  steps: [
    { stepId: 's1', position: 1, action: 'Первый', expectedResult: 'Итог 1', status: 'NOT_RUN', actualResult: null, comment: null },
    { stepId: 's2', position: 2, action: 'Второй', expectedResult: 'Итог 2', status: 'NOT_RUN', actualResult: null, comment: null },
  ],
} as unknown as RunResult;
const run = { id: 'r1', key: 'RUN-02', status: 'IN_PROGRESS' } as unknown as Run;

const form = () => resultFormOf(result);
const withSteps = (...statuses: RunResult['status'][]) => {
  const values = form();
  values.steps = values.steps.map((step, index) => ({ ...step, status: statuses[index] ?? 'NOT_RUN' }));
  return values;
};

describe('итог кейса по шагам', () => {
  test.each<[RunResult['status'][], RunResult['status']]>([
    [['PASSED', 'PASSED'], 'PASSED'],
    [['PASSED', 'FAILED'], 'FAILED'],
    [['BLOCKED', 'PASSED'], 'BLOCKED'],
    [['FAILED', 'BLOCKED'], 'FAILED'],
    [['SKIPPED', 'SKIPPED'], 'SKIPPED'],
    [['PASSED', 'SKIPPED'], 'PASSED'],
    [['PASSED', 'NOT_RUN'], 'NOT_RUN'],
    [[], 'NOT_RUN'],
  ])('%j → %s', (statuses, expected) => {
    expect(deriveStatus(statuses.map((status) => ({ status })))).toBe(expected);
  });

  test('проваленный шаг нельзя перекрыть выбранным итогом: сервер это отклонит', () => {
    expect(finalStatus({ ...withSteps('FAILED'), chosenStatus: 'PASSED' })).toBe('FAILED');
    expect(finalStatus({ ...withSteps('PASSED'), chosenStatus: 'BLOCKED' })).toBe('BLOCKED');
  });
});

describe('проверка результата', () => {
  test('у проваленного шага нужен фактический результат (110)', () => {
    expect(validateResult(withSteps('FAILED'))).toEqual({ 'steps.0.actualResult': 'У проваленного шага нужен фактический результат' });
  });

  test('неотмеченный кейс не сохраняется', () => {
    expect(validateResult(withSteps()).status).toBeTruthy();
    expect(validateResult(withSteps('PASSED')).status).toBeTruthy();
    expect(validateResult(withSteps('PASSED', 'PASSED'))).toEqual({});
  });

  test('провал без отметки шага требует факт кейса', () => {
    const values = { ...withSteps('PASSED', 'PASSED'), chosenStatus: 'FAILED' as const };
    expect(validateResult(values).actualResult).toBeTruthy();
    expect(validateResult({ ...values, actualResult: 'факт' })).toEqual({});
  });
});

describe('запрос результата', () => {
  test('шаги без отметки не отправляются, факт провала берётся из шага', () => {
    const values = withSteps('FAILED');
    values.steps[0].actualResult = ' 201 Created ';
    expect(toResultInput(values)).toEqual({
      status: 'FAILED', actualResult: null, comment: null, failureReason: null,
      steps: [{ stepId: 's1', status: 'FAILED', actualResult: '201 Created' }],
    });
  });

  test('причина отправляется только для заблокированного и пропущенного', () => {
    const values = { ...withSteps('PASSED', 'PASSED'), failureReason: 'причина' };
    expect(toResultInput(values).failureReason).toBeNull();
    expect(toResultInput({ ...values, chosenStatus: 'BLOCKED' }).failureReason).toBe('причина');
  });

  test('сообщение о дефекте различает «заведён» и «связан»', () => {
    const failed = { ...result, status: 'FAILED' } as RunResult;
    expect(defectMessage({ ...failed, defect: { id: 'd', key: 'DEF-02', created: true } })).toBe('заведён DEF-02');
    expect(defectMessage({ ...failed, defect: { id: 'd', key: 'DEF-02', created: false } })).toBe('связан с DEF-02');
    expect(defectMessage({ ...result, status: 'PASSED', defect: { id: 'd', key: 'DEF-02', created: false } })).toBeNull();
    expect(defectMessage(failed)).toBeNull();
  });
});

describe('форма результата', () => {
  const failOnStepOne = () => {
    fireEvent.change(screen.getByLabelText('Статус шага 1'), { target: { value: 'FAILED' } });
    fireEvent.change(screen.getByLabelText('Фактический результат шага 1'), { target: { value: '201 Created' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить результат' }));
  };

  test('провал показывает ссылку на заведённый, затем на связанный дефект', async () => {
    let created = true;
    const calls = mockFetch(({ method }) => {
      if (method !== 'PUT') return undefined;
      const defect = { id: 'd1', key: 'DEF-02', created };
      created = false;
      return { body: { ...result, status: 'FAILED', defect } };
    });
    const onSaved = vi.fn();
    renderScreen(<ResultForm run={run} result={result} onSaved={onSaved} />);
    failOnStepOne();
    expect(await screen.findByText(/Провал записан: заведён/, { selector: '.notice' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'DEF-02' }).getAttribute('href')).toBe('/defects/d1');
    expect(calls[0].url).toBe('/api/v1/runs/r1/results/res1');
    expect(calls[0].body).toMatchObject({ status: 'FAILED', steps: [{ stepId: 's1', status: 'FAILED', actualResult: '201 Created' }] });
    expect(onSaved).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить результат' }));
    expect(await screen.findByText(/Провал записан: связан с/, { selector: '.notice' })).toBeTruthy();
  });

  test('провал без фактического результата не отправляется', async () => {
    const calls = mockFetch(() => undefined);
    renderScreen(<ResultForm run={run} result={result} onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText('Статус шага 2'), { target: { value: 'FAILED' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить результат' }));
    expect(await screen.findByText('У проваленного шага нужен фактический результат')).toBeTruthy();
    expect(calls).toHaveLength(0);
  });

  test('RUN_FINISHED показывает код и причину сервера', async () => {
    mockFetch(() => ({ status: 409, body: { code: 'RUN_FINISHED', message: 'Прогон RUN-02 завершён, результаты не изменяются', errors: [] } }));
    renderScreen(<ResultForm run={run} result={result} onSaved={() => {}} />);
    failOnStepOne();
    expect(await screen.findByText('RUN_FINISHED')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('результаты не изменяются');
  });
});
