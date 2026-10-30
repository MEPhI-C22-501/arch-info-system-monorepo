import { listAllClassifiers, listAllEnvironments, type Classifier } from './api/admin';
import { useLoad } from './useLoad';

export type Option = { value: string; label: string };

export function optionsOf(classifiers: Classifier[] | undefined, kind: Classifier['kind'], keep?: string): Option[] {
  const values = (classifiers ?? []).filter((item) => item.kind === kind && (item.isActive || item.code === keep));
  const options = values.map((item) => ({ value: item.code, label: item.name }));
  // Значение могло быть отключено после сохранения кейса: в форме оно остаётся видимым.
  return keep && !options.some((option) => option.value === keep) ? [...options, { value: keep, label: keep }] : options;
}

export function useClassifiers() {
  return useLoad(() => listAllClassifiers(), ['classifiers']);
}

export function useActiveEnvironments() {
  return useLoad(() => listAllEnvironments({ isActive: true }), ['environments']);
}
