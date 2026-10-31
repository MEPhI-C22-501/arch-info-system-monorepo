import type { components } from './schema';
import { Page, QueryValue, request, withQuery } from './client';

export type TestCase = components['schemas']['TestCase'];
export type TestCaseInput = components['schemas']['TestCaseInput'];
export type TestCaseStatus = components['schemas']['TestCaseStatus'];
export type TestCaseVersionInfo = components['schemas']['TestCaseVersionInfo'];
export type CaseFilter = components['schemas']['CaseFilter'];
export type LastResult = components['schemas']['LastResult'];

export const listCases = (query: Record<string, QueryValue>) =>
  request<Page<TestCase>>('GET', withQuery('/test-cases', query));
export const getCase = (id: string, version?: number) =>
  request<TestCase>('GET', withQuery(`/test-cases/${id}`, { version }));
export const createCase = (input: TestCaseInput) => request<TestCase>('POST', '/test-cases', input);
export const updateCase = (id: string, input: TestCaseInput) => request<TestCase>('PUT', `/test-cases/${id}`, input);
export const deleteCase = (id: string) => request<void>('DELETE', `/test-cases/${id}`);
export const changeCaseStatus = (id: string, status: TestCaseStatus) =>
  request<TestCase>('POST', `/test-cases/${id}/status`, { status });
export const listCaseVersions = (id: string) =>
  request<{ items: TestCaseVersionInfo[] }>('GET', `/test-cases/${id}/versions`);
export const copyCases = (ids: string[]) => request<Page<TestCase>>('POST', '/test-cases/copy', { ids });
