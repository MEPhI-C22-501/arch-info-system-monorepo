import { describe, expect, it } from 'vitest';
import { errorMessage } from './errorMessages';

describe('API error messages', () => {
  it('explains server errors and iteration state conflicts in Russian', () => {
    expect(errorMessage(500, [{ field: 'request', reason: 'internal_error' }])).toBe('На сервере произошла ошибка. Попробуйте ещё раз.');
    expect(errorMessage(409, [{ field: 'state', reason: 'not_planned' }])).toContain('только запланированную итерацию');
    expect(errorMessage(409, [{ field: 'state', reason: 'not_active' }])).toContain('только активную итерацию');
  });
  it('keeps import row numbers without exposing internal error codes', () => {
    expect(errorMessage(422, [{ row: 3, field: 'plannedHours', reason: 'invalid_hours' }])).toContain('Строка 3. Плановая оценка:');
    expect(errorMessage(422, [{ field: 'request', reason: 'unknown_internal_reason' }])).not.toContain('unknown_internal_reason');
  });
});
