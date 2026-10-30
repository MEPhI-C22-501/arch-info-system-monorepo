import type { components } from './schema';
import { MAX_PAGE_SIZE, Page, QueryValue, loadAll, request, withQuery } from './client';

export type Run = components['schemas']['Run'];
export type RunInput = components['schemas']['RunInput'];
export type RunStatus = components['schemas']['RunStatus'];
export type RunResult = components['schemas']['RunResult'];
export type RunResultStep = components['schemas']['RunResultStep'];
export type ResultInput = components['schemas']['ResultInput'];
export type ResultStatus = components['schemas']['ResultStatus'];
export type RunAction = 'start' | 'complete' | 'abort';

export const listRuns = (query: Record<string, QueryValue>) => request<Page<Run>>('GET', withQuery('/runs', query));
export const getRun = (id: string) => request<Run>('GET', `/runs/${id}`);
export const createRun = (input: RunInput) => request<Run>('POST', '/runs', input);
export const changeRunStatus = (id: string, action: RunAction) => request<Run>('POST', `/runs/${id}/${action}`);
export const listRunResults = (id: string, query: Record<string, QueryValue>) =>
  request<Page<RunResult>>('GET', withQuery(`/runs/${id}/results`, query));
export const recordResult = (runId: string, resultId: string, input: ResultInput) =>
  request<RunResult>('PUT', `/runs/${runId}/results/${resultId}`, input);

// Отдельного GET для одного результата в API нет, поэтому он ищется в постраничном списке.
export async function findRunResult(runId: string, resultId: string): Promise<RunResult | undefined> {
  const results = await loadAll((page) => listRunResults(runId, { page, pageSize: MAX_PAGE_SIZE }));
  return results.find((result) => result.id === resultId);
}
