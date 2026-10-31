import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { ApiError } from '../api/client';
import { createCase } from '../api/cases';
import { listAllTemplates } from '../api/templates';
import { CaseFormValues, FieldErrors, applyTemplate, emptyCaseForm, fieldErrorsOf, toCreateInput, validateCase } from '../caseForm';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { useToast } from '../components/Toast';
import { canEditAutotest } from '../permissions';
import { useSession } from '../session';
import { useLoad } from '../useLoad';
import { useClassifiers } from '../useReferenceData';
import { CaseFields } from './CaseFields';

export function CaseCreate() {
  const { role } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const classifiers = useClassifiers();
  const templates = useLoad(() => listAllTemplates(true), ['templates']);
  const [values, setValues] = useState<CaseFormValues>(emptyCaseForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const chooseTemplate = (id: string) => {
    const template = templates.data?.find((item) => item.id === id);
    setValues(template ? applyTemplate(values, template) : { ...values, templateId: '' });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateCase(values, { isNew: true });
    setErrors(found);
    setError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const created = await createCase(toCreateInput(values));
      toast(`Кейс ${created.key} создан в статусе «Черновик»`);
      navigate(`/test-cases/${created.id}`);
    } catch (failure) {
      setError(failure);
      if (failure instanceof ApiError) setErrors(fieldErrorsOf(failure.errors));
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/test-cases">← К списку</Link></div>
      <h2>Новый тест-кейс</h2>
      <ErrorMessage error={templates.error} />
      <ErrorMessage error={error} />
      <form className="panel" onSubmit={submit}>
        <Field label="Шаблон">
          <select className="wide" value={values.templateId} onChange={(event) => chooseTemplate(event.target.value)}>
            <option value="">Без шаблона</option>
            {templates.data?.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
          </select>
        </Field>
        <CaseFields values={values} onChange={setValues} errors={errors} classifiers={classifiers.data} readOnly={false} autotestEditable={canEditAutotest(role)} moduleEditable />
        <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button type="submit" className="primary" disabled={saving}>Создать кейс</button>
        </div>
      </form>
    </>
  );
}
