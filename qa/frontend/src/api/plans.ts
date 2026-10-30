import type { components } from './schema';
import { MAX_PAGE_SIZE, Page, QueryValue, loadAll, request, withQuery } from './client';

export type TestPlan = components['schemas']['TestPlan'];
export type TestPlanInput = components['schemas']['TestPlanInput'];
export type TestPlanStatus = components['schemas']['TestPlanStatus'];
export type PlanSummary = components['schemas']['PlanSummary'];
export type PlanCasesInput = components['schemas']['PlanCasesInput'];
export type PlanAction = 'activate' | 'complete' | 'cancel';

export const listPlans = (query: Record<string, QueryValue>) => request<Page<TestPlan>>('GET', withQuery('/test-plans', query));
export const listAllPlans = (query: Record<string, QueryValue> = {}) =>
  loadAll((page) => listPlans({ ...query, page, pageSize: MAX_PAGE_SIZE }));
export const getPlan = (id: string) => request<TestPlan>('GET', `/test-plans/${id}`);
export const createPlan = (input: TestPlanInput) => request<TestPlan>('POST', '/test-plans', input);
export const addPlanCases = (id: string, input: PlanCasesInput) => request<TestPlan>('POST', `/test-plans/${id}/cases`, input);
export const removePlanCase = (id: string, caseId: string) => request<void>('DELETE', `/test-plans/${id}/cases/${caseId}`);
export const changePlanStatus = (id: string, action: PlanAction) => request<TestPlan>('POST', `/test-plans/${id}/${action}`);
export const getPlanSummary = (id: string) => request<PlanSummary>('GET', `/test-plans/${id}/summary`);
