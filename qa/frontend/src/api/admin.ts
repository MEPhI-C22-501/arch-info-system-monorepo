import type { components } from './schema';
import { MAX_PAGE_SIZE, Page, QueryValue, loadAll, request, withQuery } from './client';

export type Classifier = components['schemas']['Classifier'];
export type ClassifierInput = components['schemas']['ClassifierInput'];
export type ClassifierUpdate = components['schemas']['ClassifierUpdate'];
export type ClassifierKind = components['schemas']['ClassifierKind'];
export type Environment = components['schemas']['Environment'];
export type EnvironmentInput = components['schemas']['EnvironmentInput'];
export type EnvironmentUpdate = components['schemas']['EnvironmentUpdate'];
export type TrackerStatusMapping = components['schemas']['TrackerStatusMapping'];
export type TrackerStatusMappingItem = components['schemas']['TrackerStatusMappingItem'];

export const listAllClassifiers = (query: Record<string, QueryValue> = {}) =>
  loadAll((page) => request<Page<Classifier>>('GET', withQuery('/admin/classifiers', { ...query, page, pageSize: MAX_PAGE_SIZE })));
export const createClassifier = (input: ClassifierInput) => request<Classifier>('POST', '/admin/classifiers', input);
export const updateClassifier = (kind: ClassifierKind, code: string, input: ClassifierUpdate) =>
  request<Classifier>('PUT', `/admin/classifiers/${kind}/${encodeURIComponent(code)}`, input);
export const listAllEnvironments = (query: Record<string, QueryValue> = {}) =>
  loadAll((page) => request<Page<Environment>>('GET', withQuery('/admin/environments', { ...query, page, pageSize: MAX_PAGE_SIZE })));
export const createEnvironment = (input: EnvironmentInput) => request<Environment>('POST', '/admin/environments', input);
export const updateEnvironment = (id: string, input: EnvironmentUpdate) => request<Environment>('PUT', `/admin/environments/${id}`, input);
export const getTrackerMapping = () => request<TrackerStatusMapping>('GET', '/admin/tracker-status-mapping');
export const replaceTrackerMapping = (items: TrackerStatusMappingItem[]) =>
  request<TrackerStatusMapping>('PUT', '/admin/tracker-status-mapping', { items });
