export function Empty({ text }: { text: string }) {
  return <div className="empty"><span>◌</span><p>{text}</p></div>;
}
