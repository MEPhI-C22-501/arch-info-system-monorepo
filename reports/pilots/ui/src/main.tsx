import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App, SNAPSHOT } from './App';
import { errorMessage } from './api';
import { completeLogin, type Session } from './auth';
import './styles.css';

async function start(): Promise<void> {
  // /snapshots/<id> is served by the API for scheduled-report links; remember the id and open the app.
  const snapshot = /^\/snapshots\/([0-9a-f-]{36})$/.exec(window.location.pathname)?.[1];
  if (snapshot) {
    sessionStorage.setItem(SNAPSHOT, snapshot);
    window.history.replaceState({}, '', '/ui/');
  }
  let session: Session | null = null;
  let error = '';
  try {
    const done = await completeLogin();
    if (done) {
      session = done.session;
      window.history.replaceState({}, '', '/ui' + done.returnTo);
    }
  } catch (e) {
    error = errorMessage(e);
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <BrowserRouter basename="/ui" future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App initialSession={session} initialError={error} />
      </BrowserRouter>
    </StrictMode>,
  );
}

void start();
