import { useEffect, useState } from 'react';
import { checkHealth, HEALTH_TIMEOUT_MS } from '../lib/health';

type Status = 'checking' | 'connected' | 'unavailable';
const labels: Record<Status, string> = {
  checking: 'Checking backend', connected: 'Backend connected', unavailable: 'Backend unavailable',
};

export function ConnectionStatus() {
  const [status, setStatus] = useState<Status>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let activeController: AbortController | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      if (inFlight) return;
      inFlight = true;
      const controller = new AbortController();
      activeController = controller;
      timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
      try {
        await checkHealth(controller.signal);
        if (!disposed) setStatus('connected');
      } catch {
        if (!disposed) setStatus('unavailable');
      } finally {
        clearTimeout(timeout);
        inFlight = false;
      }
    };
    setStatus('checking');
    void refresh();
    const interval = setInterval(() => void refresh(), 10000);
    return () => {
      disposed = true;
      clearInterval(interval);
      clearTimeout(timeout);
      activeController?.abort();
    };
  }, [attempt]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span role="status" aria-live="polite" className={`status-badge status-${status}`}>
        <span className="status-dot" aria-hidden="true" />{labels[status]}
      </span>
      <button className="button-secondary" onClick={() => setAttempt(value => value + 1)}>
        Check connection
      </button>
    </div>
  );
}
