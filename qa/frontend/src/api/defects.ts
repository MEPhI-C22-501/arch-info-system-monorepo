import type { components } from './schema';
import { Page, QueryValue, request, withQuery } from './client';

export type Defect = components['schemas']['Defect'];
export type DefectDetail = components['schemas']['DefectDetail'];
export type DefectUpdate = components['schemas']['DefectUpdate'];
export type DefectStatus = components['schemas']['DefectStatus'];
export type DefectComment = components['schemas']['DefectComment'];
export type DefectHistoryEntry = components['schemas']['DefectHistoryEntry'];

export const listDefects = (query: Record<string, QueryValue>) => request<Page<Defect>>('GET', withQuery('/defects', query));
export const getDefect = (id: string) => request<DefectDetail>('GET', `/defects/${id}`);
export const updateDefect = (id: string, input: DefectUpdate) => request<DefectDetail>('PUT', `/defects/${id}`, input);
export const transitionDefect = (id: string, to: DefectStatus) => request<DefectDetail>('POST', `/defects/${id}/transitions`, { to });
export const listDefectHistory = (id: string) => request<{ items: DefectHistoryEntry[] }>('GET', `/defects/${id}/history`);
export const addDefectComment = (id: string, body: string) => request<DefectComment>('POST', `/defects/${id}/comments`, { body });
