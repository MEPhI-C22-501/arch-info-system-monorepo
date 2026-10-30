import type { components } from './schema';
import { MAX_PAGE_SIZE, Page, QueryValue, loadAll, request, withQuery } from './client';

export type Suite = components['schemas']['Suite'];
export type SuiteInput = components['schemas']['SuiteInput'];
export type SuitePurpose = components['schemas']['SuitePurpose'];

export const listSuites = (query: Record<string, QueryValue>) => request<Page<Suite>>('GET', withQuery('/suites', query));
export const listAllSuites = (query: Record<string, QueryValue> = {}) =>
  loadAll((page) => listSuites({ ...query, page, pageSize: MAX_PAGE_SIZE }));
export const getSuite = (id: string) => request<Suite>('GET', `/suites/${id}`);
export const createSuite = (input: SuiteInput) => request<Suite>('POST', '/suites', input);
export const changeSuiteStatus = (id: string, action: 'archive' | 'restore') => request<Suite>('POST', `/suites/${id}/${action}`);
