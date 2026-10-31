import { ConnectionStatus } from './components/ConnectionStatus';
import { Panel } from './components/Panel';

export default function App() {
  return (
    <div className="min-h-screen">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-5 px-6 py-6">
          <a href="#main" className="flex items-center gap-3 font-semibold tracking-tight">
            <span className="brand-mark" aria-hidden="true">▶</span>YouTube Insight Engine
          </a>
          <span className="eyebrow">Local workspace · Phase 1</span>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-6 py-12 md:py-20">
        <p className="eyebrow mb-4 text-accent">An artist. A question. A data journey.</p>
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">
          A foundation for<br /><span className="text-accent">clearer insights.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          A portfolio workspace for exploring public YouTube channels.
          The workspace is ready for development. Channel analysis comes in a later phase.
        </p>
        <Panel className="mt-10">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <h2 className="text-xl font-semibold">Workspace connection</h2>
              <p className="mt-2 max-w-xl text-muted">This indicator checks the local backend every 10 seconds.</p>
            </div>
            <ConnectionStatus />
          </div>
        </Panel>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <Panel>
            <p className="eyebrow text-accent">01 / Foundation</p>
            <h2 className="mt-4 text-xl font-semibold">Built to be understandable</h2>
            <p className="mt-3 leading-relaxed text-muted">Python and FastAPI serve the application. SQLite stores local data.
              React presents the interface. Each layer has one clear responsibility.</p>
          </Panel>
          <Panel>
            <p className="eyebrow text-accent">02 / Next chapter</p>
            <h2 className="mt-4 text-xl font-semibold">No channel data yet</h2>
            <p className="mt-3 leading-relaxed text-muted">No YouTube requests, analytics, or revenue estimates are active.
              Future collection requires a separate implementation phase and policy review.</p>
          </Panel>
        </div>
        <footer className="mt-12 border-t border-line pt-6 text-sm text-muted">
          Offline foundation · No YouTube credentials required
        </footer>
      </main>
    </div>
  );
}
