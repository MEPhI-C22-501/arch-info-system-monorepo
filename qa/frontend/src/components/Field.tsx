import { ReactNode } from 'react';

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className={error ? 'field invalid' : 'field'}>
      <span>{label}</span>
      {children}
      {error && <span className="field-error" role="alert">{error}</span>}
    </label>
  );
}

export function Prop({ name, children }: { name: string; children: ReactNode }) {
  return <><dt>{name}</dt><dd>{children || '—'}</dd></>;
}
