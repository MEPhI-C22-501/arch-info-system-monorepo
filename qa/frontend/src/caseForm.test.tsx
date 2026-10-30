import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import type { TestCase } from './api/cases';
import { applyTemplate, caseFormOf, emptyCaseForm, saveOutcome, toCreateInput, toUpdateInput, validateCase } from './caseForm';
import { newStep } from './components/StepsEditor';
import { CaseCard } from './screens/CaseCard';
import { CaseCreate } from './screens/CaseCreate';
import { mockFetch, page, renderScreen } from './test/helpers';

const original = {
  id: 'c1', key: 'TC-RM-03', status: 'ACTUAL', version: 1, currentVersion: 1, module: 'RM', title: 'Кейс', description: null, preconditions: null,
  priority: 'HIGH', severity: 'MAJOR', type: 'FUNCTIONAL', automated: false, autotestKey: null, featureRef: null, epicRef: null, requirementRef: null,
  createdBy: 'seed', createdAt: '2026-10-30T10:00:00Z', updatedAt: '2026-10-30T10:00:00Z',
  steps: [{ id: 's1', position: 1, action: 'Шаг', expectedResult: 'Итог' }], lastResult: null,
} as unknown as TestCase;

const classifiers = [
  { kind: 'PRIORITY', code: 'HIGH', name: 'Высокий', sortOrder: 1, isActive: true },
  { kind: 'SEVERITY', code: 'MAJOR', name: 'Значительный', sortOrder: 1, isActive: true },
  { kind: 'SEVERITY', code: 'MINOR', name: 'Незначительный', sortOrder: 2, isActive: true },
  { kind: 'CASE_TYPE', code: 'FUNCTIONAL', name: 'Функциональный', sortOrder: 1, isActive: true },
];

describe('проверка формы кейса', () => {
  test('обязательные поля нового кейса', () => {
    const errors = validateCase(emptyCaseForm(), { isNew: true });
    expect(Object.keys(errors).sort()).toEqual(['module', 'priority', 'severity', 'title', 'type']);
  });

  test('модуль — как в ключе TC-<модуль>-NN', () => {
    const values = { ...caseFormOf(original), module: 'r' };
    expect(validateCase(values, { isNew: true }).module).toBeTruthy();
    expect(validateCase({ ...values, module: 'INF' }, { isNew: true }).module).toBeUndefined();
  });

  test('у шага нужны действие и ожидаемый результат', () => {
    const values = { ...caseFormOf(original), steps: [newStep('Действие', ' ')] };
    expect(validateCase(values, { isNew: false })).toEqual({ 'steps.0.expectedResult': 'Укажите ожидаемый результат' });
  });

  test('актуальному кейсу нужен хотя бы один шаг', () => {
    const values = { ...caseFormOf(original), steps: [] };
    expect(validateCase(values, { isNew: false, requireSteps: true }).steps).toBeTruthy();
    expect(validateCase(values, { isNew: false }).steps).toBeUndefined();
  });

  test('автоматизированному кейсу нужен ключ автотеста', () => {
    expect(validateCase({ ...caseFormOf(original), automated: true }, { isNew: false }).autotestKey).toBeTruthy();
  });
});

describe('запрос сохранения', () => {
  test('неизменённые необязательные поля не отправляются: null не превращается в пустую строку', () => {
    const input = toUpdateInput(caseFormOf(original), original);
    expect(input.description).toBeUndefined();
    expect(input.preconditions).toBeUndefined();
    expect(input.autotestKey).toBeUndefined();
    expect(input.epicRef).toBeUndefined();
    expect(input.version).toBe(1);
    expect(input.steps).toEqual([{ action: 'Шаг', expectedResult: 'Итог' }]);
  });

  test('очищенное поле отправляется пустым', () => {
    const withText = { ...original, description: 'текст' } as TestCase;
    expect(toUpdateInput({ ...caseFormOf(withText), description: '' }, withText).description).toBe('');
  });

  test('шаблон заполняет форму и остаётся в запросе', () => {
    const values = applyTemplate(emptyCaseForm(), {
      id: 't1', name: 'Проверка API', isActive: true,
      body: { priority: 'MEDIUM', severity: 'MAJOR', type: 'FUNCTIONAL', preconditions: 'Условие', steps: [{ action: 'А', expectedResult: 'Б' }] },
    });
    const input = toCreateInput({ ...values, title: 'Новый', module: 'RM' });
    expect(input).toMatchObject({ templateId: 't1', priority: 'MEDIUM', preconditions: 'Условие', steps: [{ action: 'А', expectedResult: 'Б' }] });
  });

  test('исход сохранения различает версию, ссылки и отсутствие изменений', () => {
    expect(saveOutcome(original, { ...original, version: 2 })).toBe('new-version');
    expect(saveOutcome(original, { ...original, updatedAt: '2026-10-31T00:00:00Z' })).toBe('refs-only');
    expect(saveOutcome(original, { ...original })).toBe('unchanged');
  });
});

function mockCard(onPut: () => { status?: number; body?: unknown }) {
  return mockFetch(({ method, url }) => {
    if (url.includes('/admin/classifiers')) return page(classifiers);
    if (url.endsWith('/test-cases/c1/versions')) return { body: { items: [{ version: 1, author: 'seed', createdAt: '2026-10-30T10:00:00Z', changedFields: [] }] } };
    if (method === 'PUT' && url.endsWith('/test-cases/c1')) return onPut();
    if (url.includes('/test-cases/c1')) return { body: original };
    return undefined;
  });
}

const renderCard = () => renderScreen(<CaseCard />, { role: 'qa-tester', path: '/test-cases/c1', pattern: '/test-cases/:id' });

describe('карточка кейса', () => {
  test('сохранение без правок сообщает «версия не создана» и не шлёт описание', async () => {
    const calls = mockCard(() => ({ body: original }));
    renderCard();
    fireEvent.click(await screen.findByRole('button', { name: 'Сохранить версию' }));
    expect(await screen.findByText('Изменений нет — версия не создана')).toBeTruthy();
    const put = calls.find((call) => call.method === 'PUT')!;
    expect(put.body).toMatchObject({ version: 1, title: 'Кейс' });
    expect(put.body).not.toHaveProperty('description');
  });

  test('правка создаёт новую версию', async () => {
    mockCard(() => ({ body: { ...original, version: 2, currentVersion: 2, title: 'Новое название' } }));
    renderCard();
    const title = await screen.findByLabelText('Название');
    fireEvent.change(title, { target: { value: 'Новое название' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить версию' }));
    expect(await screen.findByText('Создана версия 2')).toBeTruthy();
  });

  test('VERSION_CONFLICT показывает причину и предлагает открыть последнюю версию', async () => {
    const calls = mockCard(() => ({ status: 409, body: { code: 'VERSION_CONFLICT', message: 'Кейс уже сохранён', errors: [{ field: 'version', reason: 'current:2' }] } }));
    renderCard();
    fireEvent.click(await screen.findByRole('button', { name: 'Сохранить версию' }));
    expect(await screen.findByText('VERSION_CONFLICT')).toBeTruthy();
    expect(screen.getByText('текущая версия 2')).toBeTruthy();
    const reads = calls.filter((call) => call.method === 'GET' && call.url.endsWith('/test-cases/c1')).length;
    fireEvent.click(screen.getByRole('button', { name: 'Открыть последнюю версию' }));
    await waitFor(() => expect(calls.filter((call) => call.method === 'GET' && call.url.endsWith('/test-cases/c1')).length).toBe(reads + 1));
  });

  test('ошибка проверки сервера подсвечивает поле', async () => {
    mockCard(() => ({ status: 422, body: { code: 'VALIDATION_FAILED', message: 'Тест-кейс не прошёл проверку', errors: [{ field: 'type', reason: 'inactive' }] } }));
    renderCard();
    fireEvent.click(await screen.findByRole('button', { name: 'Сохранить версию' }));
    expect(await screen.findByText('inactive')).toBeTruthy();
    expect(screen.getByLabelText(/^Тип/).closest('label')!.className).toContain('invalid');
  });

  test('редактор шагов: добавить, переставить, удалить', async () => {
    const calls = mockCard(() => ({ body: { ...original, version: 2, currentVersion: 2 } }));
    renderCard();
    fireEvent.click(await screen.findByRole('button', { name: 'Добавить шаг' }));
    fireEvent.change(screen.getByLabelText('Действие шага 2'), { target: { value: 'Второй' } });
    fireEvent.change(screen.getByLabelText('Ожидаемый результат шага 2'), { target: { value: 'Итог 2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Поднять шаг 2' }));
    expect((screen.getByLabelText('Действие шага 1') as HTMLTextAreaElement).value).toBe('Второй');
    fireEvent.click(screen.getByRole('button', { name: 'Удалить шаг 2' }));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить версию' }));
    await screen.findByText('Создана версия 2');
    expect(calls.find((call) => call.method === 'PUT')!.body).toMatchObject({ steps: [{ action: 'Второй', expectedResult: 'Итог 2' }] });
  });

  test('незаполненный шаг не уходит на сервер', async () => {
    const calls = mockCard(() => ({ body: original }));
    renderCard();
    fireEvent.click(await screen.findByRole('button', { name: 'Добавить шаг' }));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить версию' }));
    expect(await screen.findByText('Укажите действие')).toBeTruthy();
    expect(calls.some((call) => call.method === 'PUT')).toBe(false);
  });
});

test('создание из шаблона заполняет форму и передаёт templateId', async () => {
  const calls = mockFetch(({ method, url }) => {
    if (url.includes('/admin/classifiers')) return page(classifiers);
    if (url.includes('/templates')) {
      return page([{ id: 't1', name: 'Проверка API', isActive: true, body: { priority: 'HIGH', severity: 'MINOR', type: 'FUNCTIONAL', steps: [{ action: 'Запрос', expectedResult: 'Ответ' }] } }]);
    }
    if (method === 'POST' && url.endsWith('/test-cases')) return { status: 201, body: { ...original, id: 'c2', key: 'TC-RM-06' } };
    return undefined;
  });
  renderScreen(<CaseCreate />, { role: 'qa-tester' });
  await screen.findByRole('option', { name: 'Проверка API' });
  fireEvent.change(screen.getByLabelText('Шаблон'), { target: { value: 't1' } });
  expect((screen.getByLabelText('Действие шага 1') as HTMLTextAreaElement).value).toBe('Запрос');
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Из шаблона' } });
  fireEvent.change(screen.getByLabelText(/^Модуль/), { target: { value: 'rm' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать кейс' }));
  await screen.findByText('другой экран');
  expect(calls.find((call) => call.method === 'POST')!.body).toMatchObject({ title: 'Из шаблона', module: 'RM', templateId: 't1', severity: 'MINOR' });
});
