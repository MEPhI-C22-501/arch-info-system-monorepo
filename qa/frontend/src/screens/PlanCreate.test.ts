import { expect, test } from 'vitest';
import { validatePlan } from './PlanCreate';

const valid = { name: 'План', owner: 'ivanov', startDate: '2026-11-01', endDate: '2026-11-30', scopeKind: 'RELEASE' as const, planningProjectId: 'p', planningReleaseId: 'r' };

test('план с релизом проходит проверку', () => {
  expect(validatePlan(valid)).toEqual({});
});

test('релиз требует проект и релиз, проект — только проект, модуль — ни одного', () => {
  const noRefs = { ...valid, planningProjectId: '', planningReleaseId: '' };
  expect(Object.keys(validatePlan(noRefs)).sort()).toEqual(['planningProjectId', 'planningReleaseId']);
  expect(Object.keys(validatePlan({ ...noRefs, scopeKind: 'PROJECT' }))).toEqual(['planningProjectId']);
  expect(validatePlan({ ...noRefs, scopeKind: 'MODULE' })).toEqual({});
});

test('окончание не раньше начала', () => {
  expect(validatePlan({ ...valid, endDate: '2026-10-01' }).endDate).toBeTruthy();
  expect(validatePlan({ ...valid, endDate: valid.startDate })).toEqual({});
});
