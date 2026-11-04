import { useEffect, useState, type ReactNode } from 'react';

/** Loading indicator shown only after 300 ms, so fast answers do not flicker (110, section 1). */
export function Loading({ label = 'Загрузка…' }: { label?: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 300);
    return () => clearTimeout(timer);
  }, []);
  return <p className="state" role="status" aria-busy="true">{visible ? label : ''}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="state state-empty" role="status">{children}</p>;
}

export function Failure({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {onRetry && <button type="button" onClick={onRetry}>Повторить</button>}
    </div>
  );
}

export function Notice({ tone, children }: { tone: 'warning' | 'info' | 'success'; children: ReactNode }) {
  return <div className={`notice notice-${tone}`} role={tone === 'warning' ? 'alert' : 'status'}>{children}</div>;
}
