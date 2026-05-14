import { AlertTriangle, Check, ChevronDown, ChevronUp, FileText, X as XIcon } from 'lucide-react';
import { useState } from 'react';
import type { Diagnosis } from '../api/types';
import { EvidencePanel } from './evidence-panel';

interface DiagnosisListProps {
  diagnoses: Diagnosis[];
  onAccept: (index: number) => void;
  onReject: (index: number) => void;
}

function probabilityTone(p: number): { bar: string; badge: string; label: string } {
  if (p >= 0.7) return { bar: 'bg-teal-600', badge: 'bg-teal-50 text-teal-800 border-teal-200', label: 'High' };
  if (p >= 0.4) return { bar: 'bg-amber-500', badge: 'bg-amber-50 text-amber-800 border-amber-200', label: 'Moderate' };
  return { bar: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700 border-slate-200', label: 'Low' };
}

export function DiagnosisList({ diagnoses, onAccept, onReject }: DiagnosisListProps) {
  const [expanded, setExpanded] = useState<number | null>(0);

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-950">Ranked Differential</h3>
          <p className="mt-1 text-xs font-medium text-slate-500">Suggestions for clinician review</p>
        </div>
        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-800">
          Verify before treatment
        </span>
      </div>

      {diagnoses.map((d, i) => {
        const evidenceCount = d.evidence?.length || d.evidenceRefs.length;
        const tone = probabilityTone(d.probability);

        return (
          <article
            key={`${d.name}-${i}`}
            className={`overflow-hidden rounded-xl border bg-white shadow-sm transition-all ${
              d.accepted === true
                ? 'border-teal-300 ring-2 ring-teal-100'
                : d.accepted === false
                ? 'border-slate-200 opacity-70'
                : 'border-slate-200'
            }`}
          >
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-700">
                      {i + 1}
                    </span>
                    <h4 className="text-base font-bold text-slate-950">{d.name}</h4>
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${tone.badge}`}>
                      {tone.label}
                    </span>
                  </div>

                  <div className="mt-3 flex items-center gap-3">
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${tone.bar}`}
                        style={{ width: `${d.probability * 100}%` }}
                        role="progressbar"
                        aria-valuenow={Math.round(d.probability * 100)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${d.name} probability`}
                      />
                    </div>
                    <span className="w-12 text-right text-sm font-bold text-slate-700">
                      {Math.round(d.probability * 100)}%
                    </span>
                  </div>

                  {d.reasoning && (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-slate-500">
                        <FileText className="h-3.5 w-3.5" />
                        Clinical reasoning
                      </p>
                      <p className="mt-1 text-sm leading-6 text-slate-700">{d.reasoning}</p>
                    </div>
                  )}
                </div>

                <div className="flex flex-shrink-0 items-center gap-1">
                  <button
                    onClick={() => onAccept(i)}
                    className={`rounded-lg p-2 transition-colors ${
                      d.accepted === true
                        ? 'bg-teal-100 text-teal-800'
                        : 'text-slate-400 hover:bg-teal-50 hover:text-teal-700'
                    }`}
                    aria-label={`Accept ${d.name}`}
                    title="Accept"
                  >
                    <Check className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => onReject(i)}
                    className={`rounded-lg p-2 transition-colors ${
                      d.accepted === false
                        ? 'bg-slate-200 text-slate-600'
                        : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'
                    }`}
                    aria-label={`Reject ${d.name}`}
                    title="Reject"
                  >
                    <XIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {d.name.toLowerCase().includes('unable') && (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <span>The system returned a fallback response. Check backend health, model availability, and retrieval dependencies.</span>
                </div>
              )}

              {evidenceCount > 0 && (
                <button
                  onClick={() => setExpanded(expanded === i ? null : i)}
                  className="mt-3 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-teal-800 transition-colors hover:bg-teal-50"
                >
                  {expanded === i ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  {expanded === i ? 'Hide' : 'Show'} evidence ({evidenceCount})
                </button>
              )}
            </div>

            {expanded === i && evidenceCount > 0 && (
              <div className="border-t border-slate-100 bg-slate-50 px-4 py-3">
                <EvidencePanel refs={d.evidenceRefs} items={d.evidence} />
              </div>
            )}
          </article>
        );
      })}
    </section>
  );
}
