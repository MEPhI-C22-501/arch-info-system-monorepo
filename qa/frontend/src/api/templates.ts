import type { components } from './schema';
import { MAX_PAGE_SIZE, Page, loadAll, request, withQuery } from './client';

export type Template = components['schemas']['Template'];
export type TemplateInput = components['schemas']['TemplateInput'];

export const listAllTemplates = (isActive?: boolean) =>
  loadAll((page) => request<Page<Template>>('GET', withQuery('/templates', { isActive, page, pageSize: MAX_PAGE_SIZE })));
export const createTemplate = (input: TemplateInput) => request<Template>('POST', '/templates', input);
export const updateTemplate = (id: string, input: TemplateInput) => request<Template>('PUT', `/templates/${id}`, input);
