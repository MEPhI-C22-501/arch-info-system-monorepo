import { createContext, useContext } from 'react';
import { ROLES, hasAny, type Session } from './auth';

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('Session is required');
  return session;
}

/** What the navigation may show; the server still checks every request (110, section 4). */
export function abilities(session: Session) {
  const business = hasAny(session, ROLES.projectManager, ROLES.teamLead, ROLES.qaLead, ROLES.member, ROLES.analyst);
  return {
    reports: business,
    subscriptions: hasAny(session, ROLES.projectManager, ROLES.teamLead, ROLES.qaLead, ROLES.analyst),
    audit: hasAny(session, ROLES.admin),
    explore: hasAny(session, ROLES.analyst),
  };
}
