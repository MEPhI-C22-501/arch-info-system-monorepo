import { FormEvent, useState } from 'react';
import { Classifier, ClassifierKind, createClassifier, listAllClassifiers, updateClassifier } from '../api/admin';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { useToast } from '../components/Toast';
import { useLoad } from '../useLoad';

const KINDS: { kind: ClassifierKind; label: string }[] = [
  { kind: 'SEVERITY', label: 'Серьёзность' },
  { kind: 'PRIORITY', label: 'Приоритет кейса' },
  { kind: 'CASE_TYPE', label: 'Тип кейса' },
];
const CODE_PATTERN = /^[A-Z][A-Z0-9_]{0,31}$/;

function ClassifierRow({ item, onChanged, onError }: { item: Classifier; onChanged: () => void; onError: (error: unknown) => void }) {
  const toast = useToast();
  const [name, setName] = useState(item.name);
  const [sortOrder, setSortOrder] = useState(String(item.sortOrder));
  const dirty = name !== item.name || sortOrder !== String(item.sortOrder);

  const save = async (patch: Parameters<typeof updateClassifier>[2], message: string) => {
    onError(null);
    try {
      await updateClassifier(item.kind, item.code, patch);
      toast(message);
      onChanged();
    } catch (failure) {
      onError(failure);
    }
  };

  return (
    <tr>
      <td><code>{item.code}</code></td>
      <td><input type="text" aria-label={`Название ${item.code}`} value={name} onChange={(event) => setName(event.target.value)} /></td>
      <td><input type="number" aria-label={`Порядок ${item.code}`} value={sortOrder} onChange={(event) => setSortOrder(event.target.value)} style={{ width: 80 }} /></td>
      <td>{item.isActive ? 'да' : 'нет'}</td>
      <td>
        <div className="bar" style={{ marginBottom: 0 }}>
          <button type="button" disabled={!dirty || !name.trim()} onClick={() => save({ name: name.trim(), sortOrder: Number(sortOrder) }, `Значение ${item.code} сохранено`)}>Сохранить</button>
          <button type="button" onClick={() => save({ isActive: !item.isActive }, item.isActive ? `Значение ${item.code} отключено` : `Значение ${item.code} включено`)}>{item.isActive ? 'Отключить' : 'Включить'}</button>
        </div>
      </td>
    </tr>
  );
}

export function AdminClassifiers() {
  const toast = useToast();
  const classifiers = useLoad(() => listAllClassifiers(), ['classifiers']);
  const [kind, setKind] = useState<ClassifierKind>('SEVERITY');
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<unknown>(null);
  const items = (classifiers.data ?? []).filter((item) => item.kind === kind);
  const codeError = code && !CODE_PATTERN.test(code) ? 'Заглавные латинские буквы, цифры и подчёркивание' : undefined;

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await createClassifier({ kind, code, name: name.trim(), sortOrder: items.length + 1 });
      toast(`Значение ${code} добавлено`);
      setCode('');
      setName('');
      classifiers.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  return (
    <>
      <div className="tabs" role="tablist">
        {KINDS.map((item) => <button key={item.kind} type="button" role="tab" aria-selected={item.kind === kind} onClick={() => { setKind(item.kind); setError(null); }}>{item.label}</button>)}
      </div>
      <ErrorMessage error={error} />
      <ErrorMessage error={classifiers.error} onRetry={classifiers.reload} />
      <div className="panel">
        <table aria-busy={classifiers.loading && !classifiers.data}>
          <thead><tr><th>Код</th><th>Название</th><th>Порядок</th><th>Активно</th><th>Действия</th></tr></thead>
          <tbody>
            {classifiers.loading && !classifiers.data && <tr><td colSpan={5}><span className="skeleton" /></td></tr>}
            {classifiers.data && items.length === 0 && <tr><td colSpan={5}><div className="empty">Значений нет</div></td></tr>}
            {items.map((item) => <ClassifierRow key={`${item.code}:${item.name}:${item.sortOrder}`} item={item} onChanged={classifiers.reload} onError={setError} />)}
          </tbody>
        </table>
      </div>
      {kind === 'SEVERITY' ? (
        <p className="muted">Коды серьёзности фиксированы: можно менять название и порядок (ADR-009).</p>
      ) : (
        <form className="panel" onSubmit={create}>
          <h3>Новое значение</h3>
          <div className="fields">
            <Field label="Код" error={codeError}><input type="text" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /></Field>
            <Field label="Название"><input type="text" value={name} onChange={(event) => setName(event.target.value)} /></Field>
          </div>
          <button type="submit" className="primary" disabled={!code || !!codeError || !name.trim()}>Добавить</button>
        </form>
      )}
    </>
  );
}
