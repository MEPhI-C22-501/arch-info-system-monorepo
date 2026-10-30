import { FormEvent, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { listAllPlans } from '../api/plans';
import { createRun } from '../api/runs';
import { listAllSuites } from '../api/suites';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { useToast } from '../components/Toast';
import { useLoad } from '../useLoad';
import { useActiveEnvironments } from '../useReferenceData';

export function RunCreate() {
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const suites = useLoad(() => listAllSuites({ status: 'ACTIVE' }), ['suites']);
  const plans = useLoad(() => listAllPlans({ status: 'ACTIVE' }), ['plans']);
  const environments = useActiveEnvironments();
  const [kind, setKind] = useState<'suite' | 'plan'>(params.get('planId') ? 'plan' : 'suite');
  const [suiteId, setSuiteId] = useState(params.get('suiteId') ?? '');
  const [planId, setPlanId] = useState(params.get('planId') ?? '');
  const [environment, setEnvironment] = useState('');
  const [start, setStart] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const chosenEnvironment = environment || environments.data?.[0]?.code || '';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const source = kind === 'suite' ? suiteId : planId;
    const found = {
      ...(source ? {} : { source: kind === 'suite' ? 'Выберите набор' : 'Выберите план' }),
      ...(chosenEnvironment ? {} : { environment: 'Выберите окружение' }),
    };
    setErrors(found);
    setError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const run = await createRun({ ...(kind === 'suite' ? { suiteId } : { planId }), environment: chosenEnvironment, start });
      toast(start ? `Прогон ${run.key} запущен, версии кейсов зафиксированы` : `Прогон ${run.key} создан, версии кейсов зафиксированы`);
      navigate(`/runs/${run.id}`);
    } catch (failure) {
      setError(failure);
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/runs">← К списку</Link></div>
      <h2>Новый прогон</h2>
      <ErrorMessage error={suites.error ?? plans.error ?? environments.error} />
      <ErrorMessage error={error} />
      <form className="panel" onSubmit={submit}>
        <fieldset style={{ border: 0, padding: 0, margin: '0 0 10px' }}>
          <legend className="muted">Источник</legend>
          <label className="check"><input type="radio" name="source" checked={kind === 'suite'} onChange={() => setKind('suite')} /> Из набора</label>
          <label className="check"><input type="radio" name="source" checked={kind === 'plan'} onChange={() => setKind('plan')} /> Из тест-плана</label>
        </fieldset>
        {/* key: варианты приходят после значения из адреса, а React выставит его только новому select. */}
        {kind === 'suite' ? (
          <Field label="Набор" error={errors.source}>
            <select key={suites.data?.length ?? 0} className="wide" value={suiteId} onChange={(event) => setSuiteId(event.target.value)}>
              <option value="">—</option>
              {suites.data?.map((suite) => <option key={suite.id} value={suite.id}>{suite.name} (кейсов: {suite.caseCount})</option>)}
            </select>
          </Field>
        ) : (
          <Field label="План" error={errors.source}>
            <select key={plans.data?.length ?? 0} className="wide" value={planId} onChange={(event) => setPlanId(event.target.value)}>
              <option value="">—</option>
              {plans.data?.map((plan) => <option key={plan.id} value={plan.id}>{plan.key} {plan.name} (кейсов: {plan.caseCount})</option>)}
            </select>
          </Field>
        )}
        <Field label="Окружение" error={errors.environment}>
          <select className="wide" value={chosenEnvironment} onChange={(event) => setEnvironment(event.target.value)}>
            {environments.data?.map((item) => <option key={item.id} value={item.code}>{item.code} — {item.name}</option>)}
          </select>
        </Field>
        <label className="check"><input type="checkbox" checked={start} onChange={(event) => setStart(event.target.checked)} /> Сразу запустить</label>
        <div className="bar" style={{ marginBottom: 0 }}>
          <button type="submit" className="primary" disabled={saving}>Создать прогон</button>
        </div>
      </form>
    </>
  );
}
