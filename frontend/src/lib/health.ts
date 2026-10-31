export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const HEALTH_TIMEOUT_MS = 4000;

export async function checkHealth(signal: AbortSignal): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    signal, cache: 'no-store', credentials: 'omit', headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('Backend unavailable');
  const body: unknown = await response.json();
  if (typeof body !== 'object' || body === null || !('status' in body) || body.status !== 'ok') {
    throw new Error('Unexpected health response');
  }
}
