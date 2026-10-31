import type { TestCase, TestCaseInput } from './api/cases';
import type { Template } from './api/templates';
import { newStep } from './components/StepsEditor';
import { MODULE_OPTIONS } from './labels';

export type StepDraft = { draftId: number; action: string; expectedResult: string };

export type CaseFormValues = {
  title: string;
  module: string;
  description: string;
  preconditions: string;
  priority: string;
  severity: string;
  type: string;
  automated: boolean;
  autotestKey: string;
  featureRef: string;
  epicRef: string;
  requirementRef: string;
  templateId: string;
  steps: StepDraft[];
};

export type FieldErrors = Record<string, string>;

const REQUIRED = 'Обязательное поле';

export const isKnownModule = (module: string) => MODULE_OPTIONS.some((option) => option.value === module);

export function emptyCaseForm(): CaseFormValues {
  return {
    title: '', module: '', description: '', preconditions: '', priority: '', severity: '', type: '',
    automated: false, autotestKey: '', featureRef: '', epicRef: '', requirementRef: '', templateId: '', steps: [],
  };
}

export function caseFormOf(testCase: TestCase): CaseFormValues {
  return {
    title: testCase.title,
    module: testCase.module,
    description: testCase.description ?? '',
    preconditions: testCase.preconditions ?? '',
    priority: testCase.priority,
    severity: testCase.severity,
    type: testCase.type,
    automated: testCase.automated ?? false,
    autotestKey: testCase.autotestKey ?? '',
    featureRef: testCase.featureRef ?? '',
    epicRef: testCase.epicRef ?? '',
    requirementRef: testCase.requirementRef ?? '',
    templateId: '',
    steps: (testCase.steps ?? []).map((step) => newStep(step.action, step.expectedResult)),
  };
}

export function applyTemplate(values: CaseFormValues, template: Template): CaseFormValues {
  const { body } = template;
  return {
    ...values,
    templateId: template.id,
    description: body.description ?? values.description,
    preconditions: body.preconditions ?? values.preconditions,
    priority: body.priority ?? values.priority,
    severity: body.severity ?? values.severity,
    type: body.type ?? values.type,
    steps: (body.steps ?? []).map((step) => newStep(step.action, step.expectedResult)),
  };
}

export function validateCase(values: CaseFormValues, options: { isNew: boolean; requireSteps?: boolean }): FieldErrors {
  const errors: FieldErrors = {};
  if (!values.title.trim()) errors.title = REQUIRED;
  if (options.isNew && !isKnownModule(values.module)) errors.module = 'Выберите модуль';
  for (const field of ['priority', 'severity', 'type'] as const) {
    if (!values[field]) errors[field] = REQUIRED;
  }
  if (values.automated && !values.autotestKey.trim()) errors.autotestKey = 'У автоматизированного кейса нужен ключ автотеста';
  values.steps.forEach((step, index) => {
    if (!step.action.trim()) errors[`steps.${index}.action`] = 'Укажите действие';
    if (!step.expectedResult.trim()) errors[`steps.${index}.expectedResult`] = 'Укажите ожидаемый результат';
  });
  if (options.requireSteps && values.steps.length === 0) errors.steps = 'У актуального кейса должен быть хотя бы один шаг';
  return errors;
}

const stepsInput = (values: CaseFormValues) => values.steps.map(({ action, expectedResult }) => ({ action, expectedResult }));

export function toCreateInput(values: CaseFormValues): TestCaseInput {
  return {
    title: values.title,
    module: values.module,
    description: values.description || undefined,
    preconditions: values.preconditions || undefined,
    priority: values.priority,
    severity: values.severity as TestCaseInput['severity'],
    type: values.type,
    automated: values.automated,
    autotestKey: values.autotestKey || undefined,
    featureRef: values.featureRef || undefined,
    epicRef: values.epicRef || undefined,
    requirementRef: values.requirementRef || undefined,
    templateId: values.templateId || undefined,
    steps: stepsInput(values),
  };
}

// Неизменённые необязательные поля не отправляются: сервер оставит их как есть, а пустая строка
// вместо null создала бы лишнюю версию и нарушила «без изменений — версия не создана».
export function toUpdateInput(values: CaseFormValues, original: TestCase): TestCaseInput {
  const changed = (value: string, current?: string | null) => (value === (current ?? '') ? undefined : value);
  return {
    title: values.title,
    module: original.module,
    description: changed(values.description, original.description),
    preconditions: changed(values.preconditions, original.preconditions),
    priority: values.priority,
    severity: values.severity as TestCaseInput['severity'],
    type: values.type,
    automated: values.automated,
    autotestKey: changed(values.autotestKey, original.autotestKey),
    featureRef: changed(values.featureRef, original.featureRef),
    epicRef: changed(values.epicRef, original.epicRef),
    requirementRef: changed(values.requirementRef, original.requirementRef),
    steps: stepsInput(values),
    version: original.version,
  };
}

export type SaveOutcome = 'new-version' | 'refs-only' | 'unchanged';

export function saveOutcome(before: TestCase, after: TestCase): SaveOutcome {
  if (after.version !== before.version) return 'new-version';
  return after.updatedAt !== before.updatedAt ? 'refs-only' : 'unchanged';
}

// Поля ошибки 422 сервера — те же, что в форме (title, steps.0.action).
export function fieldErrorsOf(items: { field?: string; reason?: string }[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const { field, reason } of items) {
    if (field) errors[field] = reason === 'required' ? REQUIRED : reason ?? '';
  }
  return errors;
}
