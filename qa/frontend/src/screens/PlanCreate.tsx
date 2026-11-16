import { request, type Page } from '../api/client';
import type { Person } from '../usePeople';
import { useLoad } from '../useLoad';
import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { ApiError } from '../api/client';
import { TestPlanInput, createPlan } from '../api/plans';
import { FieldErrors, fieldErrorsOf } from '../caseForm';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { useToast } from '../components/Toast';
import { SCOPE_LABELS } from '../labels';
import { useSession, sessionSubject } from '../session';

type Scope = TestPlanInput['scopeKind'];
const TEXT_REFS = [
  ['planningProjectId', 'Проект Planning System'],
  ['planningReleaseId', 'Релиз (logicalItemId)'],
  ['planningMilestoneId', 'Веха (logicalItemId)'],
  ['trackerIterationId', 'Итерация Task Tracker'],
  ['scopeRef', 'Модуль'],
  ['teamRef', 'Команда'],
] as const;

export function validatePlan(values: Pick<TestPlanInput, 'name' | 'owner' | 'startDate' | 'endDate' | 'scopeKind' | 'planningProjectId' | 'planningReleaseId'>): FieldErrors {
  const errors: FieldErrors = {};
  if (!values.name.trim()) errors.name = 'Обязательное поле';
  if (!values.owner.trim()) errors.owner = 'Обязательное поле';
  if (!values.startDate) errors.startDate = 'Обязательное поле';
  if (!values.endDate) errors.endDate = 'Обязательное поле';
  if (values.startDate && values.endDate && values.endDate < values.startDate) errors.endDate = 'Окончание раньше начала';
  if ((values.scopeKind === 'RELEASE' || values.scopeKind === 'PROJECT') && !values.planningProjectId?.trim()) errors.planningProjectId = 'Обязательное поле для этой области';
  if (values.scopeKind === 'RELEASE' && !values.planningReleaseId?.trim()) errors.planningReleaseId = 'Обязательное поле для релиза';
  return errors;
}

export function PlanCreate() {
  const session = useSession();
  const directory = 'accessToken' in session;
  const [query, setQuery] = useState('');
  const people = useLoad(() => directory ? request<Page<Person>>('GET',
    '/profiles/assignees?pageSize=50&q=' + encodeURIComponent(query)) : Promise.resolve(null), [directory, query]);
  const navigate = useNavigate();
  const toast = useToast();
  const [values, setValues] = useState({
    name: '', scopeKind: 'RELEASE' as Scope, owner: directory ? '' : sessionSubject(session), startDate: '', endDate: '',
    planningProjectId: '', planningReleaseId: '', planningMilestoneId: '', trackerIterationId: '', scopeRef: '', teamRef: '',
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const set = (name: keyof typeof values, value: string) => setValues({ ...values, [name]: value });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validatePlan(values);
    setErrors(found);
    setError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const plan = await createPlan(values);
      toast(`План ${plan.key} создан в статусе «Черновик»`);
      navigate(`/plans/${plan.id}`);
    } catch (failure) {
      setError(failure);
      if (failure instanceof ApiError) setErrors(fieldErrorsOf(failure.errors));
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/plans">← К списку</Link></div>
      <h2>Новый план</h2>
      <ErrorMessage error={error} />
      <form className="panel" onSubmit={submit}>
        <Field label="Название" error={errors.name}><input type="text" value={values.name} onChange={(event) => set('name', event.target.value)} /></Field>
        <div className="fields">
          <Field label="Область" error={errors.scopeKind}>
            <select className="wide" value={values.scopeKind} onChange={(event) => set('scopeKind', event.target.value)}>
              {Object.entries(SCOPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <Field label="Ответственный" error={errors.owner}>
            {directory ? (
              <>
                <input type="search" aria-label="Поиск сотрудника" value={query} onChange={event => setQuery(event.target.value)} />
                <select value={values.owner} onChange={event => set('owner', event.target.value)}>
                  <option value="">Выберите сотрудника</option>
                  {people.data?.items.map(p => <option value={p.accountUserId} key={p.accountUserId}>{p.displayName}</option>)}
                </select>
              </>
            ) : <input type="text" value={values.owner} onChange={event => set('owner', event.target.value)} />}
          </Field>
          <Field label="Начало" error={errors.startDate}><input type="date" value={values.startDate} onChange={(event) => set('startDate', event.target.value)} /></Field>
          <Field label="Окончание" error={errors.endDate}><input type="date" value={values.endDate} onChange={(event) => set('endDate', event.target.value)} /></Field>
        </div>
        <h3>Привязка</h3>
        <p className="muted">Справочника Planning System пока нет: значения вводятся вручную и помечаются «не проверена».</p>
        <div className="fields">
          {TEXT_REFS.map(([name, label]) => (
            <Field key={name} label={label} error={errors[name]}><input type="text" value={values[name]} onChange={(event) => set(name, event.target.value)} /></Field>
          ))}
        </div>
        <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button type="submit" className="primary" disabled={saving}>Создать план</button>
        </div>
      </form>
    </>
  );
}
