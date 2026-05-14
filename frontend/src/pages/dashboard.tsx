import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Activity, ArrowRight, Clock, Database, PlusCircle, Server, ShieldCheck } from 'lucide-react';
import { ConsultationCardSkeleton } from '../components/loading-skeleton';
import type { ConsultationSummary } from '../api/types';
import { useAuth } from '../features/auth/auth-context';

function healthTone(ok?: boolean) {
  return ok
    ? 'border-teal-200 bg-teal-50 text-teal-800'
    : 'border-amber-200 bg-amber-50 text-amber-800';
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: consultations, isLoading, error } = useQuery({
    queryKey: ['consultations'],
    queryFn: () => api.listConsultations(),
  });
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health(),
    retry: 1,
    staleTime: 20_000,
  });

  const recent = (consultations || []).slice(0, 5);
  const completed = (consultations || []).filter((c) => c.status === 'completed').length;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              Evidence-grounded clinical support
            </div>
            <h2 className="text-2xl font-bold tracking-normal text-slate-950 lg:text-3xl">
              Welcome back, {user?.name || 'Doctor'}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Start a consultation, review retrieved STG evidence, and keep the final clinical decision clearly under your control.
            </p>
          </div>

          <button
            onClick={() => navigate('/consultation/new')}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-teal-800"
          >
            <PlusCircle className="h-4 w-4" />
            New Consultation
          </button>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">Consultations</p>
              <p className="mt-2 text-2xl font-bold text-slate-950">{consultations?.length ?? 0}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-500">{completed} completed, {Math.max((consultations?.length ?? 0) - completed, 0)} draft</p>
        </div>

        <div className={`rounded-lg border p-4 shadow-sm ${healthTone(health?.chroma.healthy)}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] opacity-75">Knowledge base</p>
              <p className="mt-2 text-2xl font-bold">{health?.chroma.indexed_chunks ?? 3724}</p>
            </div>
            <Database className="h-8 w-8 opacity-80" />
          </div>
          <p className="mt-3 text-xs opacity-80">Tanzania STG chunks indexed for retrieval</p>
        </div>

        <div className={`rounded-lg border p-4 shadow-sm ${healthTone(health?.llm.healthy)}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] opacity-75">AI service</p>
              <p className="mt-2 text-lg font-bold">{health?.llm.model || 'Checking...'}</p>
            </div>
            <Server className="h-8 w-8 opacity-80" />
          </div>
          <p className="mt-3 text-xs opacity-80">{health?.llm.provider || 'Provider'} status: {health?.llm.healthy ? 'healthy' : 'verify before demo'}</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_0.8fr]">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-950">Recent Consultations</h3>
              <p className="text-xs text-slate-500">Open a draft or review completed work</p>
            </div>
            {consultations && consultations.length > 0 && (
              <button
                onClick={() => navigate('/history')}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-teal-800 transition-colors hover:bg-teal-50"
              >
                View all <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {isLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <ConsultationCardSkeleton key={i} />
              ))}
            </div>
          )}

          {error && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-700">
              Failed to load consultations.
            </p>
          )}

          {consultations && consultations.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center">
              <Clock className="mx-auto mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm font-semibold text-slate-700">No consultations yet</p>
              <button
                onClick={() => navigate('/consultation/new')}
                className="mt-3 text-sm font-bold text-teal-800 hover:text-teal-900"
              >
                Start your first consultation
              </button>
            </div>
          )}

          {recent.length > 0 && (
            <div className="space-y-2">
              {recent.map((c: ConsultationSummary) => (
                <button
                  key={c.id}
                  onClick={() => navigate(`/consultation/${c.id}`)}
                  className="group flex w-full items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 text-left transition-all hover:border-teal-300 hover:bg-teal-50/40"
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

        <div className="rounded-xl border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-teal-300" />
            <h3 className="text-base font-bold">Clinical Assurance</h3>
          </div>
          <div className="mt-5 space-y-4">
            {[
              ['Evidence traceability', 'Every diagnosis can show the supporting STG passage.'],
              ['Human-in-the-loop', 'Accept and reject controls make clinical ownership visible.'],
              ['Operational clarity', 'System, LLM, and knowledge-base status are easy to scan.'],
            ].map(([title, body]) => (
              <div key={title} className="border-l-2 border-teal-300 pl-3">
                <p className="text-sm font-bold text-white">{title}</p>
                <p className="mt-1 text-xs leading-5 text-slate-300">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
