import type { ResultInput, ResultStatus, RunResult } from './api/runs';
import type { FieldErrors } from './caseForm';

export type StepValue = {
  stepId: string;
  position: number;
  action: string;
  expectedResult: string;
  status: ResultStatus;
  actualResult: string;
};

export type ResultFormValues = {
  steps: StepValue[];
  // Итог, выбранный явно; пусто — итог считается по шагам.
  chosenStatus: ResultStatus | '';
  actualResult: string;
  comment: string;
  failureReason: string;
};

export function resultFormOf(result: RunResult): ResultFormValues {
  const steps = result.steps.map((step) => ({
    stepId: step.stepId,
    position: step.position,
    action: step.action,
    expectedResult: step.expectedResult,
    status: step.status,
    actualResult: step.actualResult ?? '',
  }));
  const derived = deriveStatus(steps);
  return {
    steps,
    chosenStatus: result.status !== 'NOT_RUN' && result.status !== derived ? result.status : '',
    actualResult: steps.some((step) => step.status === 'FAILED') ? '' : result.actualResult ?? '',
    comment: result.comment ?? '',
    failureReason: result.failureReason ?? '',
  };
}

export function deriveStatus(steps: Pick<StepValue, 'status'>[]): ResultStatus {
  const statuses = steps.map((step) => step.status);
  if (statuses.includes('FAILED')) return 'FAILED';
  if (statuses.includes('BLOCKED')) return 'BLOCKED';
  if (statuses.length === 0 || statuses.includes('NOT_RUN')) return 'NOT_RUN';
  return statuses.includes('PASSED') ? 'PASSED' : 'SKIPPED';
}

// Проваленный шаг определяет итог: сервер отклоняет иной статус при FAILED у шага.
export function finalStatus(values: ResultFormValues): ResultStatus {
  const derived = deriveStatus(values.steps);
  return derived === 'FAILED' ? 'FAILED' : values.chosenStatus || derived;
}

export function validateResult(values: ResultFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const status = finalStatus(values);
  if (status === 'NOT_RUN') errors.status = 'Отметьте все шаги или выберите итог кейса';
  values.steps.forEach((step, index) => {
    if (step.status === 'FAILED' && !step.actualResult.trim()) {
      errors[`steps.${index}.actualResult`] = 'У проваленного шага нужен фактический результат';
    }
  });
  if (status === 'FAILED' && !values.steps.some((step) => step.status === 'FAILED') && !values.actualResult.trim()) {
    errors.actualResult = 'У проваленного кейса нужен фактический результат';
  }
  return errors;
}

export function toResultInput(values: ResultFormValues): ResultInput {
  const status = finalStatus(values);
  const hasFailedStep = values.steps.some((step) => step.status === 'FAILED');
  return {
    status,
    // Факт кейса сервер берёт из первого проваленного шага.
    actualResult: status === 'FAILED' && !hasFailedStep ? values.actualResult : null,
    comment: values.comment.trim() || null,
    failureReason: status === 'BLOCKED' || status === 'SKIPPED' ? values.failureReason.trim() || null : null,
    // steps заменяет прежний набор; шаг без отметки сервер и так покажет как NOT_RUN.
    steps: values.steps
      .filter((step) => step.status !== 'NOT_RUN')
      .map((step) => ({ stepId: step.stepId, status: step.status, actualResult: step.actualResult.trim() || null })),
  };
}

// Поле created приходит только в ответе PUT, который завёл дефект (FR-DEF-02, FR-DEF-03).
export function defectMessage(result: RunResult): string | null {
  if (result.status !== 'FAILED' || !result.defect) return null;
  return result.defect.created ? `заведён ${result.defect.key}` : `связан с ${result.defect.key}`;
}
