import { useEffect, useState } from 'react';
import { request } from './api/client';
import { useSession } from './session';

export type Person = { accountUserId: string; displayName: string };

export function usePeople(subjects: Array<string | null | undefined>) {
  const directory = 'accessToken' in useSession();
  const key = JSON.stringify([...new Set(subjects.filter((value): value is string => !!value))].sort());
  const [snapshot, setSnapshot] = useState<{ key: string; names: Record<string, string> }>();

  useEffect(() => {
    if (!directory) return;
    const ids: string[] = JSON.parse(key);
    if (!ids.length) return;
    let active = true;
    const batches = [];
    for (let start = 0; start < ids.length; start += 100) {
      batches.push(request<Person[]>('POST', '/profiles/resolve', { subjects: ids.slice(start, start + 100) }));
    }
    void Promise.all(batches).then(pages => {
      if (active) setSnapshot({ key, names: Object.fromEntries(pages.flat().map(p => [p.accountUserId, p.displayName])) });
    }).catch(() => {});
    return () => { active = false; };
  }, [directory, key]);

  return (subject?: string | null) => {
    if (!subject) return '—';
    if (!directory) return subject;
    const name = snapshot?.key === key ? snapshot.names[subject] : undefined;
    return name || `Профиль не найден (${subject})`;
  };
}
