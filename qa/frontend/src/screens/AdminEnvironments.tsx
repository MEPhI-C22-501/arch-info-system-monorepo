import { FormEvent, useState } from 'react';
import { Environment, createEnvironment, listAllEnvironments, updateEnvironment } from '../api/admin';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { useToast } from '../components/Toast';
import { useLoad } from '../useLoad';

const CODE_PATTERN = /^[a-z][a-z0-9-]{0,31}$/;

// Адреса подсистем редактируются строками «имя=адрес».
export function formatBaseUrls(urls: Record<string, string>): string {
  return Object.entries(urls).map(([name, url]) => `${name}=${url}`).join('\n');
}

export function parseBaseUrls(text: string): Record<string, string> {
  const urls: Record<string, string> = {};
  for (const line of text.split('\n')) {
    const [name, ...rest] = line.split('=');
    if (name.trim()) urls[name.trim()] = rest.join('=').trim();
  }
  return urls;
}

function EnvironmentRow({ item, onChanged, onError }: { item: Environment; onChanged: () => void; onError: (error: unknown) => void }) {
  const toast = useToast();
  const [name, setName] = useState(item.name);
  const [urls, setUrls] = useState(formatBaseUrls(item.baseUrls));
  const dirty = name !== item.name || urls !== formatBaseUrls(item.baseUrls);

  const save = async (patch: Parameters<typeof updateEnvironment>[1], message: string) => {
    onError(null);
    try {
      await updateEnvironment(item.id, patch);
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
      <td><textarea rows={2} aria-label={`Адреса ${item.code}`} value={urls} onChange={(event) => setUrls(event.target.value)} /></td>
      <td>{item.isActive ? 'да' : 'нет'}</td>
      <td>
        <div className="bar" style={{ marginBottom: 0 }}>
          <button type="button" disabled={!dirty || !name.trim()} onClick={() => save({ name: name.trim(), baseUrls: parseBaseUrls(urls) }, `Окружение ${item.code} сохранено`)}>Сохранить</button>
          <button type="button" onClick={() => save({ isActive: !item.isActive }, item.isActive ? `Окружение ${item.code} отключено` : `Окружение ${item.code} включено`)}>{item.isActive ? 'Отключить' : 'Включить'}</button>
        </div>
      </td>
    </tr>
  );
}

export function AdminEnvironments() {
  const toast = useToast();
  const environments = useLoad(() => listAllEnvironments(), ['environments']);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [urls, setUrls] = useState('');
  const [error, setError] = useState<unknown>(null);
  const codeError = code && !CODE_PATTERN.test(code) ? 'Строчные латинские буквы, цифры и дефис' : undefined;

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await createEnvironment({ code, name: name.trim(), baseUrls: parseBaseUrls(urls) });
      toast(`Окружение ${code} добавлено`);
      setCode('');
      setName('');
      setUrls('');
      environments.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  return (
    <>
      <ErrorMessage error={error} />
      <ErrorMessage error={environments.error} onRetry={environments.reload} />
      <div className="panel">
        <table aria-busy={environments.loading && !environments.data}>
          <thead><tr><th>Код</th><th>Название</th><th>Адреса подсистем (имя=адрес)</th><th>Активно</th><th>Действия</th></tr></thead>
          <tbody>
            {environments.loading && !environments.data && <tr><td colSpan={5}><span className="skeleton" /></td></tr>}
            {environments.data?.length === 0 && <tr><td colSpan={5}><div className="empty">Окружений нет</div></td></tr>}
            {environments.data?.map((item) => <EnvironmentRow key={`${item.id}:${item.name}:${formatBaseUrls(item.baseUrls)}`} item={item} onChanged={environments.reload} onError={setError} />)}
          </tbody>
        </table>
      </div>
      <form className="panel" onSubmit={create}>
        <h3>Новое окружение</h3>
        <div className="fields">
          <Field label="Код (не меняется)" error={codeError}><input type="text" value={code} onChange={(event) => setCode(event.target.value)} /></Field>
          <Field label="Название"><input type="text" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        </div>
        <Field label="Адреса подсистем (имя=адрес, по одному в строке)"><textarea rows={2} value={urls} onChange={(event) => setUrls(event.target.value)} /></Field>
        <button type="submit" className="primary" disabled={!code || !!codeError || !name.trim()}>Добавить</button>
      </form>
    </>
  );
}
