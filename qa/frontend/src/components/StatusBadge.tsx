import { StatusKind, statusLabel } from '../labels';

// Цвет дублируется текстом (110, раздел 1).
export function StatusBadge({ status, kind }: { status: string; kind?: StatusKind }) {
  return <span className={`tag ${status}`}>{statusLabel(status, kind)}</span>;
}
