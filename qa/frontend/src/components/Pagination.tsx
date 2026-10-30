export function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (page: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <nav className="bar" aria-label="Страницы" style={{ marginTop: 10, marginBottom: 0 }}>
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>← Назад</button>
      <span>Страница {page} из {totalPages}</span>
      <button type="button" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Вперёд →</button>
    </nav>
  );
}
