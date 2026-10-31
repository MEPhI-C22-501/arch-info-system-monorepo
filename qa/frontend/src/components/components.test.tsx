import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { ApiError } from '../api/client';
import { caseFilterFields, caseListQuery, describeCaseFilter } from '../caseFilter';
import { CasesList } from '../screens/CasesList';
import { mockFetch, page, renderScreen } from '../test/helpers';
import { Column, DataTable } from './DataTable';
import { FilterBar } from './FilterBar';
import { ErrorMessage, formatErrorItem } from './ErrorMessage';
import { Pagination } from './Pagination';
import { StatusBadge } from './StatusBadge';

type Row = { id: string; title: string };
const COLUMNS: Column<Row>[] = [{ header: 'Название', render: (row) => <>{row.title} <a href="#x">ссылка</a></> }];
const ROWS = [{ id: '1', title: 'Первая' }];

describe('DataTable', () => {
  test('строка открывается щелчком и по Enter', () => {
    const onOpen = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} onOpen={onOpen} emptyText="Пусто" />);
    const row = screen.getByText(/Первая/).closest('tr')!;
    expect(row.tabIndex).toBe(0);
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: 'Enter' });
    fireEvent.keyDown(row, { key: ' ' });
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  test('щелчок по ссылке и флажку в строке её не открывает', () => {
    const onOpen = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} onOpen={onOpen} emptyText="Пусто" selection={{ selected: new Set(), onChange: () => {} }} />);
    fireEvent.click(screen.getByRole('link', { name: 'ссылка' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Выбрать 1' }));
    expect(onOpen).not.toHaveBeenCalled();
  });

  test('состояния: загрузка, пусто, ошибка с повтором', () => {
    const { rerender } = render(<DataTable columns={COLUMNS} rows={undefined} rowKey={(row) => row.id} loading emptyText="Пусто" />);
    expect(screen.getAllByTestId('skeleton-row').length).toBeGreaterThan(0);
    rerender(<DataTable columns={COLUMNS} rows={[]} rowKey={(row) => row.id} emptyText="Пусто" />);
    expect(screen.getByText('Пусто')).toBeTruthy();
    const onRetry = vi.fn();
    rerender(<DataTable columns={COLUMNS} rows={undefined} rowKey={(row) => row.id} error={new ApiError(500, 'INTERNAL', 'Внутренняя ошибка')} onRetry={onRetry} emptyText="Пусто" />);
    expect(screen.getByText('INTERNAL')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  test('«выбрать все» выбирает строки страницы', () => {
    const onChange = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} emptyText="Пусто" selection={{ selected: new Set(), onChange }} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Выбрать все на странице' }));
    expect([...onChange.mock.calls[0][0]]).toEqual(['1']);
  });

  test('строка, которую нельзя выбрать, остаётся без галочки и не входит в «выбрать все»', () => {
    const onChange = vi.fn();
    const rows = [...ROWS, { id: '2', title: 'Вторая' }];
    render(<DataTable columns={COLUMNS} rows={rows} rowKey={(row) => row.id} emptyText="Пусто" selection={{ selected: new Set(), onChange }} isSelectable={(row) => row.id === '1'} />);
    expect(screen.queryByRole('checkbox', { name: 'Выбрать 2' })).toBeNull();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Выбрать все на странице' }));
    expect([...onChange.mock.calls[0][0]]).toEqual(['1']);
  });
});

describe('ErrorMessage', () => {
  test('показывает код, причину и перечень', () => {
    render(<ErrorMessage error={new ApiError(409, 'VALUE_IN_USE', 'Значение используется', [{ field: 'isActive', reason: 'used-by:case:TC-RM-01' }, { field: 'isActive', reason: 'used-by:template:Проверка API' }])} />);
    expect(screen.getByText('VALUE_IN_USE')).toBeTruthy();
    expect(screen.getByText('кейс TC-RM-01')).toBeTruthy();
    expect(screen.getByText('шаблон Проверка API')).toBeTruthy();
  });

  test.each([
    [{ field: 'to', reason: 'allowed:CLOSED,REOPENED' }, 'допустимо: CLOSED, REOPENED'],
    [{ field: 'to', reason: 'open-auto:DEF-03' }, 'незакрытый автодефект DEF-03'],
    [{ field: 'runs', reason: 'unfinished:RUN-02' }, 'не завершён RUN-02'],
    [{ field: 'suiteId', reason: 'running:RUN-02' }, 'выполняется RUN-02'],
    [{ field: 'title', reason: 'required' }, 'title: обязательное поле'],
    [{ field: 'filter', reason: 'TC-RM-06:DRAFT' }, 'TC-RM-06:DRAFT'],
    [{ field: 'ids.0', reason: 'TC-RM-06:DRAFT' }, 'ids.0: TC-RM-06:DRAFT'],
  ])('%j → %s', (item, expected) => {
    expect(formatErrorItem(item)).toBe(expected);
  });

  test('без ошибки ничего не выводит', () => {
    const { container } = render(<ErrorMessage error={null} />);
    expect(container.firstChild).toBeNull();
  });
});

test('значение фильтра из адреса видно, даже если варианты пришли позже', () => {
  const props = { values: { type: 'SMOKE' }, onChange: () => {} };
  const field = { name: 'type', label: 'Тип', type: 'select' as const, emptyLabel: 'Все' };
  const { rerender } = render(<FilterBar {...props} fields={[{ ...field, options: [] }]} />);
  rerender(<FilterBar {...props} fields={[{ ...field, options: [{ value: 'SMOKE', label: 'Smoke' }] }]} />);
  expect((screen.getByLabelText(/^Тип/) as HTMLSelectElement).value).toBe('SMOKE');
});

describe('текстовый фильтр', () => {
  const field = [{ name: 'q', label: 'Поиск', type: 'text' as const }];

  test('Enter применяет значение и не отправляет форму вокруг', () => {
    const onChange = vi.fn();
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(<form onSubmit={onSubmit}><FilterBar fields={field} values={{}} onChange={onChange} /></form>);
    const input = screen.getByLabelText('Поиск');
    fireEvent.change(input, { target: { value: ' api ' } });
    const notPrevented = fireEvent.keyDown(input, { key: 'Enter' });
    expect(notPrevented).toBe(false);
    expect(onChange).toHaveBeenCalledWith('q', 'api');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test('уход из поля сразу применяет набранное: кнопка рядом видит актуальный фильтр', () => {
    const onChange = vi.fn();
    render(<FilterBar fields={field} values={{}} onChange={onChange} />);
    const input = screen.getByLabelText('Поиск');
    fireEvent.change(input, { target: { value: 'api' } });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.blur(input);
    expect(onChange).toHaveBeenCalledExactlyOnceWith('q', 'api');
  });
});

test('Pagination скрыта на одной странице и ограничена по краям', () => {
  const onChange = vi.fn();
  const { container, rerender } = render(<Pagination page={1} totalPages={1} onChange={onChange} />);
  expect(container.firstChild).toBeNull();
  rerender(<Pagination page={1} totalPages={3} onChange={onChange} />);
  expect((screen.getByRole('button', { name: '← Назад' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Вперёд →' }));
  expect(onChange).toHaveBeenCalledWith(2);
});

test('StatusBadge дублирует цвет текстом и различает смысл IN_PROGRESS', () => {
  const { rerender } = render(<StatusBadge status="IN_PROGRESS" />);
  expect(screen.getByText('Выполняется').className).toBe('tag IN_PROGRESS');
  rerender(<StatusBadge status="IN_PROGRESS" kind="defect" />);
  expect(screen.getByText('В работе')).toBeTruthy();
});

test('«Все» по статусу уходит в запрос как includeArchived', () => {
  expect(caseListQuery({ status: 'ALL', module: 'RM' })).toEqual({ module: 'RM', includeArchived: true });
  expect(caseListQuery({ status: 'ARCHIVED' })).toEqual({ status: 'ARCHIVED' });
});

test('«Все, включая архивные» есть только у списка кейсов', () => {
  const statusOptions = (withArchived: boolean) => {
    const field = caseFilterFields([], withArchived).find((item) => item.name === 'status');
    return field?.type === 'select' ? field.options.map((option) => option.value) : [];
  };
  expect(statusOptions(true)).toContain('ALL');
  expect(statusOptions(false)).not.toContain('ALL');
});

test('условие набора не показывает незаданные поля', () => {
  const filter = { module: null, status: null, automated: true, q: 'api' } as unknown as Parameters<typeof describeCaseFilter>[0];
  expect(describeCaseFilter(filter)).toBe('автоматизирован, поиск: api');
  expect(describeCaseFilter(null)).toBe('—');
});

describe('список кейсов', () => {
  test('пустой результат фильтра', async () => {
    mockFetch(({ url }) => (url.includes('/test-cases') || url.includes('/admin/classifiers') ? page([]) : undefined));
    renderScreen(<CasesList />, { path: '/?module=RM', pattern: '/' });
    expect(await screen.findByText('По фильтру кейсов нет')).toBeTruthy();
  });

  test('ошибка загрузки показывает код сервера', async () => {
    mockFetch(({ url }) => {
      if (url.includes('/admin/classifiers')) return page([]);
      return { status: 503, body: { code: 'DATABASE_UNAVAILABLE', message: 'База данных недоступна', errors: [] } };
    });
    renderScreen(<CasesList />);
    expect(await screen.findByText('DATABASE_UNAVAILABLE')).toBeTruthy();
  });

  test('смена фильтра сбрасывает страницу и уходит в запрос', async () => {
    const calls = mockFetch(({ url }) => (url.includes('/test-cases') || url.includes('/admin/classifiers') ? page([]) : undefined));
    renderScreen(<CasesList />, { path: '/?page=3' });
    await screen.findByText('По фильтру кейсов нет');
    expect(calls.some((call) => call.url.includes('/test-cases?page=3'))).toBe(true);
    fireEvent.change(screen.getByLabelText('Статус'), { target: { value: 'ARCHIVED' } });
    await vi.waitFor(() => expect(calls.at(-1)!.url).toBe('/api/v1/test-cases?status=ARCHIVED&page=1'));
  });

  test('массовое копирование отправляет выбранные и сообщает ключи', async () => {
    const calls = mockFetch(({ method, url }) => {
      if (method === 'POST') return { status: 201, body: { items: [{ key: 'TC-RM-06' }], page: 1, pageSize: 1, totalPages: 1 } };
      if (url.includes('/admin/classifiers')) return page([]);
      if (url.includes('/test-cases')) return page([{ id: 'c1', key: 'TC-RM-01', title: 'Кейс', type: 'SMOKE', severity: 'MAJOR', version: 1, status: 'ACTUAL' }]);
      return undefined;
    });
    renderScreen(<CasesList />, { role: 'qa-tester' });
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Выбрать c1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Копировать выбранные (1)' }));
    expect(await screen.findByText('Созданы копии: TC-RM-06')).toBeTruthy();
    expect(calls.find((call) => call.method === 'POST')!.body).toEqual({ ids: ['c1'] });
  });
});
