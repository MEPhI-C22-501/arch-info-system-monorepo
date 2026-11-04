import { afterEach, describe, expect, it, vi } from 'vitest';
import { decodeSession } from '../auth';
import { duration, formatCell, noteText, numericValue, staleSources, weekStart } from '../format';
import { describeQuery } from '../pages/ReportPage';
import { describeSchedule } from '../pages/Subscriptions';

const token = (claims: object) => 'h.' + btoa(unescape(encodeURIComponent(JSON.stringify(claims)))).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_') + '.s';

describe('format', () => {
  it('formats numbers, missing values and nested measures', () => {
    expect(formatCell(11.25)).toBe('11,25');
    expect(formatCell(null)).toBe('не задано');
    expect(formatCell({ id: null, label: 'не задано' })).toBe('не задано');
    expect(formatCell({ opened: 1, closed: 1 })).toBe('Создано: 1; Закрыто: 1');
    expect(formatCell('PARTIAL')).toBe('Неполные данные');
  });
  it('finds the first number inside nested measures', () => {
    expect(numericValue({ cycleMedian: 3, cycleP85: 4 })).toBe(3);
    expect(numericValue({ id: 'x', label: 'Проект' })).toBeNull();
  });
  it('explains notes and stale sources', () => {
    expect(noteText('MISSING_MAPPING:planning-project')).toContain('соответствие');
    expect(staleSources([{ source: 'qa-system', stream: 'reports', dataAsOf: null, lagSeconds: null, thresholdSeconds: 3600, state: 'STALE' }]))
      .toEqual(['Данные источника «Тестирование» ещё не загружены']);
    expect(staleSources([{ source: 'task-tracker', stream: 'reports', dataAsOf: '2026-10-05T07:00:00Z', lagSeconds: 7200, thresholdSeconds: 3600, state: 'STALE' }]))
      .toEqual(['Данные источника «Трекер задач» актуальны на 05.10.2026, 10:00 МСК, задержка 2 ч']);
  });
  it('rounds the lag to the largest unit', () => {
    expect([duration(45), duration(720), duration(7200), duration(null)]).toEqual(['45 с', '12 мин', '2 ч', 'нет данных']);
  });
});

describe('default period', () => {
  afterEach(() => vi.useRealTimers());
  it('starts on Monday of the current Moscow week', () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-04T22:30:00Z')); // Thursday 01:30 in Moscow
    expect(weekStart()).toBe('2026-11-02');
    vi.setSystemTime(new Date('2026-11-01T12:00:00Z')); // Sunday
    expect(weekStart()).toBe('2026-10-26');
  });
  it('names the parameters of an empty result', () => {
    expect(describeQuery({ params: { periodFrom: '2026-11-02', periodTo: '2026-11-04', projectIds: ['p-1'] }, slice: ['employee'] }))
      .toBe('период 2026-11-02 — 2026-11-04, разрез «Сотрудник», проекты: p-1');
  });
});

describe('session', () => {
  it('reads Reports roles from the token and ignores malformed ones', () => {
    const s = decodeSession(token({ sub: 'u-1', preferred_username: 'анна', exp: 1, resource_access: { reports: { roles: ['reports-member', 7] } } }));
    expect([...s.roles]).toEqual(['reports-member']);
    expect(s.name).toBe('анна');
    expect(decodeSession(token({ sub: 'u-2', exp: 1 })).roles.size).toBe(0);
  });
});

describe('subscriptions', () => {
  it('describes the schedules the form creates', () => {
    expect(describeSchedule('0 9 * * *')).toBe('Ежедневно в 09:00');
    expect(describeSchedule('30 8 * * 1')).toBe('Еженедельно, понедельник в 08:30');
    expect(describeSchedule('0 9 1 * *')).toBe('Ежемесячно, 1-го числа в 09:00');
    expect(describeSchedule('*/5 * * * *')).toBe('Расписание cron: */5 * * * *');
  });
});
