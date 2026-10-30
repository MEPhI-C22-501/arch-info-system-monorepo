import { FormEvent, useState } from 'react';
import { Field } from '../components/Field';
import { ROLE_LABELS } from '../labels';
import { ROLES, Role, Session, isValidName, saveSession } from '../session';

// Демонстрационный вход: роль и имя становятся токеном. Keycloak подключается в TECH-09.
export function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [role, setRole] = useState<Role>('qa-lead');
  const [name, setName] = useState('ivanov');
  const [error, setError] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!isValidName(trimmed)) {
      setError('Имя — латинские буквы, цифры, точка, дефис или подчёркивание');
      return;
    }
    const session = { role, name: trimmed };
    saveSession(session);
    onLogin(session);
  };

  return (
    <main>
      <form className="panel login" onSubmit={submit}>
        <h1>QA System</h1>
        <p className="muted">Демо-вход: выберите роль и имя. Вход через Keycloak появится позже.</p>
        <Field label="Роль">
          <select className="wide" value={role} onChange={(event) => setRole(event.target.value as Role)}>
            {ROLES.map((value) => <option key={value} value={value}>{ROLE_LABELS[value]} ({value})</option>)}
          </select>
        </Field>
        <Field label="Имя" error={error}>
          <input type="text" autoComplete="username" value={name} onChange={(event) => setName(event.target.value)} />
        </Field>
        <button type="submit" className="primary">Войти</button>
      </form>
    </main>
  );
}
