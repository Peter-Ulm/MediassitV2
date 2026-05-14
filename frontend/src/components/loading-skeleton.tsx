export function DiagnosisSkeleton() {
  return (
    <div className="space-y-3 animate-pulse" role="status" aria-label="Loading diagnoses">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-5 w-7 rounded-full bg-slate-200" />
            <div className="h-4 w-28 rounded bg-slate-200" />
            <div className="h-5 w-16 rounded-full bg-slate-200" />
          </div>
          <div className="h-2.5 w-full rounded-full bg-slate-100">
            <div className="h-2.5 rounded-full bg-slate-200" style={{ width: `${70 - i * 20}%` }} />
          </div>
        </div>
      ))}
      <p className="sr-only">Loading diagnosis results...</p>
    </div>
  );
}

export function ConsultationCardSkeleton() {
  return (
    <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 h-4 w-3/4 rounded bg-slate-200" />
      <div className="mb-3 h-3 w-1/2 rounded bg-slate-100" />
      <div className="h-3 w-1/3 rounded bg-slate-100" />
    </div>
  );
}
