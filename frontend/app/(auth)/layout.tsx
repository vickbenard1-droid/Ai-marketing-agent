export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-signal font-mono text-sm font-semibold text-white">
            A
          </div>
          <span className="text-sm font-medium tracking-wide text-ink-200">
            AI MARKETING AGENT
          </span>
        </div>
        <div className="rounded-lg border border-ink-800 bg-ink-900 p-6 shadow-panel">
          {children}
        </div>
      </div>
    </div>
  );
}
