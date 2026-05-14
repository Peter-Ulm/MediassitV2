import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { ArrowRight, Clock, Search } from 'lucide-react';
import { useState } from 'react';
import { ConsultationCardSkeleton } from '../components/loading-skeleton';
import type { ConsultationSummary } from '../api/types';

export function HistoryPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const { data: consultations, isLoading } = useQuery({
    queryKey: ['consultations'],
    queryFn: () => api.listConsultations(),
  });

  const filtered = (consultations || []).filter((c: ConsultationSummary) =>
    c.summary.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-2xl font-bold tracking-normal text-slate-950">Consultation History</h2>
        <p className="mt-1 text-sm text-slate-500">Draft and completed diagnostic sessions</p>
      </section>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search consultations..."
          className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-4 text-sm shadow-sm focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <ConsultationCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-12 text-center shadow-sm">
          <Clock className="mx-auto mb-3 h-10 w-10 text-slate-300" />
          <p className="text-sm font-semibold text-slate-600">
            {search ? 'No consultations match your search' : 'No consultations yet'}
          </p>
        </div>
      )}

      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((c: ConsultationSummary) => (
            <button
              key={c.id}
              onClick={() => navigate(`/consultation/${c.id}`)}
              className="group flex w-full items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:border-teal-300 hover:bg-teal-50/40"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900">{c.summary}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {c.patient.age}y, {c.patient.sex} ·{' '}
                  {new Date(c.createdAt).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                </p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                    c.status === 'completed'
                      ? 'bg-teal-50 text-teal-800'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {c.status === 'completed' ? 'Completed' : 'Draft'}
                </span>
                <ArrowRight className="h-4 w-4 text-slate-300 transition-colors group-hover:text-teal-700" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
