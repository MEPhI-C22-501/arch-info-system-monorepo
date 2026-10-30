import { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react';

type Message = { text: string; isError: boolean };
type ToastFn = (text: string, isError?: boolean) => void;

const ToastContext = createContext<ToastFn>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<Message | null>(null);
  const toast = useCallback<ToastFn>((text, isError = false) => setMessage({ text, isError }), []);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), 4500);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div role="status" aria-live="polite">
        {message && <div className={message.isError ? 'toast err' : 'toast'}>{message.text}</div>}
      </div>
    </ToastContext.Provider>
  );
}
