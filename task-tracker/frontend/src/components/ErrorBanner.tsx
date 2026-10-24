export function ErrorBanner({ message, clear }: { message: string; clear?: () => void }) {
  return message ? <div className="error-banner" role="alert"><span>{message}</span>{clear && <button onClick={clear}>Закрыть</button>}</div> : null;
}
