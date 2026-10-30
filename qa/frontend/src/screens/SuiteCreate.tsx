import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { createSuite } from '../api/suites';
import { caseFilterFields, toCaseFilter } from '../caseFilter';
import { CasePicker } from '../components/CasePicker';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { FilterBar } from '../components/FilterBar';
import { useToast } from '../components/Toast';
import { useClassifiers } from '../useReferenceData';

export function SuiteCreate() {
  const navigate = useNavigate();
  const toast = useToast();
  const classifiers = useClassifiers();
  const [name, setName] = useState('');
  const [kind, setKind] = useState<'MANUAL' | 'FILTER'>('MANUAL');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<Record<string, string>>({});
  const [nameError, setNameError] = useState('');
  const [filterError, setFilterError] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const caseFilter = toCaseFilter(filter);
    const noName = !name.trim();
    const noFilter = kind === 'FILTER' && Object.keys(caseFilter).length === 0;
    setNameError(noName ? 'Обязательное поле' : '');
    setFilterError(noFilter ? 'Задайте хотя бы одно условие' : '');
    setError(null);
    if (noName || noFilter) return;
    setSaving(true);
    try {
      const suite = await createSuite(kind === 'MANUAL'
        ? { name, kind, caseIds: [...selected] }
        : { name, kind, filter: caseFilter });
      toast(`Набор «${suite.name}» создан: кейсов ${suite.caseCount}`);
      navigate(`/suites/${suite.id}`);
    } catch (failure) {
      setError(failure);
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/suites">← К списку</Link></div>
      <h2>Новый набор</h2>
      <ErrorMessage error={error} />
      <form className="panel" onSubmit={submit}>
        <Field label="Название" error={nameError}><input type="text" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <fieldset style={{ border: 0, padding: 0, margin: '0 0 10px' }}>
          <legend className="muted">Вид набора</legend>
          <label className="check"><input type="radio" name="kind" checked={kind === 'MANUAL'} onChange={() => setKind('MANUAL')} /> Ручной: состав выбирается по кейсам</label>
          <label className="check"><input type="radio" name="kind" checked={kind === 'FILTER'} onChange={() => setKind('FILTER')} /> По фильтру: состав считается при создании прогона</label>
        </fieldset>
        {kind === 'MANUAL' ? (
          <CasePicker selected={selected} onChange={setSelected} />
        ) : (
          <>
            <FilterBar fields={caseFilterFields(classifiers.data)} values={filter} onChange={(field, value) => setFilter({ ...filter, [field]: value })} />
            {filterError && <span className="field-error" role="alert">{filterError}</span>}
          </>
        )}
        <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button type="submit" className="primary" disabled={saving}>Создать набор</button>
        </div>
      </form>
    </>
  );
}
