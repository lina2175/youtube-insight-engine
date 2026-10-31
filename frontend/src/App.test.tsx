import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { API_BASE_URL, HEALTH_TIMEOUT_MS } from './lib/health';

const healthy = () => new Response(JSON.stringify({ status: 'ok' }), { status: 200 });

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('application shell and real health contract', () => {
  it('shows checking until a valid backend response arrives', async () => {
    let resolve!: (response: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>(done => { resolve = done; }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect(screen.getByRole('status')).toHaveTextContent('Checking backend');
    expect(screen.getByText('No channel data yet')).toBeInTheDocument();
    resolve(healthy());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Backend connected'));
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/health`, expect.objectContaining({ credentials: 'omit', cache: 'no-store' }));
  });

  it.each([
    ['HTTP failure', () => Promise.resolve(new Response('{}', { status: 503 }))],
    ['invalid contract', () => Promise.resolve(new Response('{"status":"wrong"}'))],
    ['invalid JSON', () => Promise.resolve(new Response('not json'))],
    ['network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('shows unavailable on %s', async (_name, response) => {
    vi.stubGlobal('fetch', vi.fn(response));
    render(<App />);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Backend unavailable'));
  });

  it('recovers when the user checks again', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(healthy());
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await screen.findByText('Backend unavailable');
    await userEvent.click(screen.getByRole('button', { name: 'Check connection' }));
    await screen.findByText('Backend connected');
  });

  it('polls so a stopped backend does not remain connected', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(healthy()).mockRejectedValue(new TypeError('offline')));
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByRole('status')).toHaveTextContent('Backend connected');
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(screen.getByRole('status')).toHaveTextContent('Backend unavailable');
  });

  it('times out a hung request and aborts requests on unmount', async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => {
      const signal = options.signal as AbortSignal;
      signals.push(signal);
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      });
    }));
    const { unmount } = render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(HEALTH_TIMEOUT_MS); });
    expect(screen.getByRole('status')).toHaveTextContent('Backend unavailable');
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    unmount();
    expect(signals.every(signal => signal.aborted)).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
});
