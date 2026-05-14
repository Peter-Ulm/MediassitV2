import { FlaskConical } from 'lucide-react';
import type { RecommendedTest } from '../api/types';

interface RecommendedTestsProps {
  tests: RecommendedTest[];
}

export function RecommendedTests({ tests }: RecommendedTestsProps) {
  if (tests.length === 0) return null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="flex items-center gap-2 text-sm font-bold text-slate-950">
        <FlaskConical className="h-4 w-4 text-teal-700" /> Recommended Tests
      </h3>
      <div className="mt-3 space-y-2">
        {tests.map((t, i) => (
          <div key={i} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <div className="min-w-0">
              <span className="text-sm font-bold text-slate-900">{t.test}</span>
              <p className="mt-1 text-xs leading-5 text-slate-600">{t.rationale}</p>
            </div>
            <button
              className="flex-shrink-0 rounded-lg border border-teal-200 bg-white px-3 py-1.5 text-xs font-bold text-teal-800 transition-colors hover:bg-teal-50"
              title="Lab ordering is not connected in this demo"
            >
              Queue
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
