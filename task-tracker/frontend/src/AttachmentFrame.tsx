export function AttachmentFrame({ name, url }: { name: string; url: string }) {
  return <iframe sandbox="" title={name} src={url}/>;
}
