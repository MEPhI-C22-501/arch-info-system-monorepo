import { describe, expect, it, vi } from 'vitest';
import { describeHistoryEntry } from './historyDiff';
import type { HistoryEntry, HistoryNames } from './historyDiff';

vi.mock('../../api', () => ({
  typeName: (value: string) => value === 'TASK' ? 'Задача' : value,
  date: (value: string) => value,
  hours: (value: number) => `${value} ч`,
}));

const names: HistoryNames = {
  users: new Map([['person-a', 'Анна'], ['person-b', 'Иван']]),
  statuses: new Map([['status-open', 'Бэклог'], ['status-progress', 'В работе']]),
  priorities: new Map(), iterations: new Map([['iteration-a', 'Итерация 7']]),
  attachments: new Map(), timeLogs: new Map(),
};
const entry = (oldValues: unknown, newValues: unknown): HistoryEntry => ({
  id: 'entry', actorId: 'person-a', occurredAt: '2026-11-22T10:00:00Z', oldValues, newValues,
});

describe('card history', () => {
  it('shows names and a readable diff for existing database-shaped records', () => {
    const result = describeHistoryEntry(entry(
      { type: 'jsonb', value: '{"statusId":"status-open","assigneeId":"person-a"}' },
      '{"statusId":"status-progress","assigneeId":"person-b","internalId":"raw-id"}',
    ), names);
    expect(result.actor).toBe('Анна');
    expect(result.changes).toEqual([
      { field: 'statusId', label: 'Статус', before: 'Бэклог', after: 'В работе' },
      { field: 'assigneeId', label: 'Исполнитель', before: 'Анна', after: 'Иван' },
    ]);
  });

  it('distinguishes adding and removing a task in an iteration or hierarchy', () => {
    const added = describeHistoryEntry(entry({ iterationId: '' }, { iterationId: 'iteration-a' }), names);
    expect(added.title).toBe('Задача добавлена в итерацию');
    expect(added.changes[0]).toMatchObject({ before: '—', after: 'Итерация 7' });
    const removed = describeHistoryEntry(entry({ iterationId: 'iteration-a' }, { iterationId: '' }), names);
    expect(removed.title).toBe('Задача исключена из итерации');
    expect(removed.changes[0]).toMatchObject({ before: 'Итерация 7', after: '—' });
    const detached = describeHistoryEntry({
      ...entry({ parentId: 'parent-a' }, { parentId: null }), relatedItems: { 'parent-a': 'Эпик разработки' },
    }, names);
    expect(detached.title).toBe('Задача откреплена от родителя');
    expect(detached.changes[0]).toMatchObject({ before: 'Эпик разработки', after: '—' });
  });

  it('keeps the removed file name and hides unknown reference identifiers', () => {
    const file = describeHistoryEntry(entry({}, { attachmentRemoved: 'file-id', attachmentName: 'отчёт.xlsx' }), names);
    expect(file.title).toBe('Откреплён файл');
    expect(file.actions[0].detail).toBe('отчёт.xlsx');

    const status = describeHistoryEntry(entry({}, { statusId: 'missing-status-id' }), names);
    expect(status.changes[0].after).toBe('Статус недоступен');
    expect(describeHistoryEntry(entry('broken JSON', null), names).changes).toEqual([]);
  });

  it('ignores legacy entries caused only by a different number format', () => {
    expect(describeHistoryEntry(entry({ plannedHours: '4.00' }, { plannedHours: 4 }), names).visible).toBe(false);
  });
});
