import { describe, expect, it } from 'vitest';
import { compareAssignee } from './metrics';

describe('iteration plan–fact', () => {
  it('shows actual effort and overrun against the frozen baseline', () => {
    expect(compareAssignee(
      { userId: 'one', plannedHours: 8, actualHours: 0, availableHours: 10 },
      { userId: 'one', plannedHours: 6, actualHours: 11, availableHours: 10 },
    )).toEqual({ planned: 8, currentPlan: 6, actual: 11, deviation: 3, available: 10 });
  });

  it('keeps baseline for an item no longer present at completion', () => {
    expect(compareAssignee({ userId: 'one', plannedHours: 5, actualHours: 0, availableHours: 8 }))
      .toEqual({ planned: 5, currentPlan: 0, actual: 0, deviation: -5, available: 8 });
  });
});
