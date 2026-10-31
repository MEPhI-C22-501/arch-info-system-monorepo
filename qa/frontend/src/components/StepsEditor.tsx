import type { StepDraft } from '../caseForm';

type Props = {
  steps: StepDraft[];
  onChange: (steps: StepDraft[]) => void;
  errors?: Record<string, string>;
  readOnly?: boolean;
};

let nextStepId = 1;
export const newStep = (action = '', expectedResult = ''): StepDraft => ({ draftId: nextStepId++, action, expectedResult });

export function StepsEditor({ steps, onChange, errors = {}, readOnly }: Props) {
  const patch = (index: number, value: Partial<StepDraft>) => onChange(steps.map((step, i) => (i === index ? { ...step, ...value } : step)));
  const move = (index: number, delta: number) => {
    const next = [...steps];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    onChange(next);
  };

  return (
    <>
      <table>
        <thead><tr><th>№</th><th>Действие</th><th>Ожидаемый результат</th>{!readOnly && <th />}</tr></thead>
        <tbody>
          {steps.length === 0 && <tr><td colSpan={4} className="muted">Шагов нет</td></tr>}
          {steps.map((step, index) => {
            const actionError = errors[`steps.${index}.action`];
            const expectedError = errors[`steps.${index}.expectedResult`];
            return (
              <tr key={step.draftId}>
                <td>{index + 1}</td>
                {readOnly ? (
                  <><td><pre>{step.action}</pre></td><td><pre>{step.expectedResult}</pre></td></>
                ) : (
                  <>
                    <td>
                      <textarea rows={2} aria-label={`Действие шага ${index + 1}`} className={actionError ? 'invalid' : undefined} value={step.action} onChange={(event) => patch(index, { action: event.target.value })} />
                      {actionError && <span className="field-error" role="alert">{actionError}</span>}
                    </td>
                    <td>
                      <textarea rows={2} aria-label={`Ожидаемый результат шага ${index + 1}`} className={expectedError ? 'invalid' : undefined} value={step.expectedResult} onChange={(event) => patch(index, { expectedResult: event.target.value })} />
                      {expectedError && <span className="field-error" role="alert">{expectedError}</span>}
                    </td>
                    <td className="step-actions">
                      <button type="button" aria-label={`Поднять шаг ${index + 1}`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button>{' '}
                      <button type="button" aria-label={`Опустить шаг ${index + 1}`} disabled={index === steps.length - 1} onClick={() => move(index, 1)}>↓</button>{' '}
                      <button type="button" aria-label={`Удалить шаг ${index + 1}`} onClick={() => onChange(steps.filter((_, i) => i !== index))}>✕</button>
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {errors.steps && <span className="field-error" role="alert">{errors.steps}</span>}
      {!readOnly && <div className="bar" style={{ marginTop: 8, marginBottom: 0 }}><button type="button" onClick={() => onChange([...steps, newStep()])}>Добавить шаг</button></div>}
    </>
  );
}
