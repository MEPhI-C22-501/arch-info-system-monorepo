import type { ReactNode } from 'react';

export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
