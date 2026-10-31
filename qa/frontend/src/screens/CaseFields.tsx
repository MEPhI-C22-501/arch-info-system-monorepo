import type { Classifier } from '../api/admin';
import { CaseFormValues, FieldErrors } from '../caseForm';
import { Field } from '../components/Field';
import { StepsEditor } from '../components/StepsEditor';
import { optionsOf } from '../useReferenceData';

type Props = {
  values: CaseFormValues;
  onChange: (values: CaseFormValues) => void;
  errors: FieldErrors;
  classifiers: Classifier[] | undefined;
  readOnly: boolean;
  autotestEditable: boolean;
  moduleEditable?: boolean;
};

// Поля кейса: одна форма для создания, карточки и просмотра версии. Поля «фактический результат»
// здесь нет намеренно: факт записывается в прогоне (ADR-014).
export function CaseFields({ values, onChange, errors, classifiers, readOnly, autotestEditable, moduleEditable }: Props) {
  const set = <K extends keyof CaseFormValues>(name: K, value: CaseFormValues[K]) => onChange({ ...values, [name]: value });
  const text = (name: 'title' | 'featureRef' | 'epicRef' | 'requirementRef' | 'autotestKey') => ({
    type: 'text',
    disabled: readOnly,
    value: values[name],
    onChange: (event: { target: { value: string } }) => set(name, event.target.value),
  });
  const select = (name: 'priority' | 'severity' | 'type', kind: Classifier['kind'], label: string) => (
    <Field label={label} error={errors[name]}>
      <select className="wide" disabled={readOnly} value={values[name]} onChange={(event) => set(name, event.target.value)}>
        <option value="">—</option>
        {optionsOf(classifiers, kind, values[name]).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </Field>
  );

  return (
    <>
      <Field label="Название" error={errors.title}><input {...text('title')} /></Field>
      <div className="fields">
        <Field label="Модуль" error={errors.module}>
          <input type="text" disabled={!moduleEditable} value={values.module} list="module-hints" onChange={(event) => set('module', event.target.value.toUpperCase())} />
        </Field>
        {select('priority', 'PRIORITY', 'Приоритет')}
        {select('severity', 'SEVERITY', 'Серьёзность')}
        {select('type', 'CASE_TYPE', 'Тип')}
      </div>
      <Field label="Описание" error={errors.description}>
        <textarea rows={2} disabled={readOnly} value={values.description} onChange={(event) => set('description', event.target.value)} />
      </Field>
      <Field label="Предусловия" error={errors.preconditions}>
        <textarea rows={2} disabled={readOnly} value={values.preconditions} onChange={(event) => set('preconditions', event.target.value)} />
      </Field>
      <div className="fields">
        <Field label="Фича" error={errors.featureRef}><input {...text('featureRef')} /></Field>
        <Field label="Эпик" error={errors.epicRef}><input {...text('epicRef')} /></Field>
        <Field label="Требование" error={errors.requirementRef}><input {...text('requirementRef')} /></Field>
      </div>
      <div className="fields">
        <label className="check">
          <input type="checkbox" disabled={readOnly || !autotestEditable} checked={values.automated} onChange={(event) => set('automated', event.target.checked)} />
          Автоматизирован
        </label>
        <Field label="Ключ автотеста" error={errors.autotestKey}>
          <input {...text('autotestKey')} disabled={readOnly || !autotestEditable} />
        </Field>
      </div>
      <h3>Шаги</h3>
      <StepsEditor steps={values.steps} onChange={(steps) => set('steps', steps)} errors={errors} readOnly={readOnly} />
    </>
  );
}
