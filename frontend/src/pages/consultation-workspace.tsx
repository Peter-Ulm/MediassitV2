import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { Consultation, Diagnosis } from '../api/types';
import { SymptomInput } from '../components/symptom-input';
import { PatientCard } from '../components/patient-card';
import { DiagnosisList } from '../components/diagnosis-list';
import { FollowUpSuggestions } from '../components/follow-up-suggestions';
import { RecommendedTests } from '../components/recommended-tests';
import { ActionBar } from '../components/action-bar';
import { DiagnosisSkeleton } from '../components/loading-skeleton';
import { useToast } from '../components/toast';
import { AlertTriangle, Clock, FileText, Gauge, ShieldCheck } from 'lucide-react';

export function ConsultationWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [symptoms, setSymptoms] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api
      .getConsultation(id)
      .then((c) => {
        setConsultation(c);
        setSymptoms(c.symptoms);
        setNotes(c.notes || '');
      })
      .catch(() => addToast('error', 'Failed to load consultation'))
      .finally(() => setLoading(false));
  }, [addToast, id]);

  const handleRunAnalysis = useCallback(async () => {
    if (!consultation || !symptoms.trim()) return;
    setAnalyzing(true);
    try {
      const result = await api.generateDiagnosis(symptoms, consultation.patient);
      setConsultation({
        ...consultation,
        symptoms,
        results: result,
      });
      addToast('success', 'Analysis complete. Review the evidence before accepting.');
    } catch {
      addToast('error', 'Analysis failed. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  }, [addToast, consultation, symptoms]);

  const handleAccept = useCallback(
    (index: number) => {
      if (!consultation) return;
      const diagnoses = consultation.results.diagnoses.map((d: Diagnosis, i: number) =>
        i === index ? { ...d, accepted: d.accepted === true ? null : true } : d
      );
      setConsultation({
        ...consultation,
        results: { ...consultation.results, diagnoses },
      });
    },
    [consultation]
  );

  const handleReject = useCallback(
    (index: number) => {
      if (!consultation) return;
      const diagnoses = consultation.results.diagnoses.map((d: Diagnosis, i: number) =>
        i === index ? { ...d, accepted: d.accepted === false ? null : false } : d
      );
      setConsultation({
        ...consultation,
        results: { ...consultation.results, diagnoses },
      });
    },
    [consultation]
  );

  const handleAppendFollowUp = useCallback((question: string) => {
    setSymptoms((prev) => (prev ? `${prev}; ${question}` : question));
  }, []);

  const handleSave = useCallback(async () => {
    if (!consultation) return;
    setSaving(true);
    try {
      const saved = await api.updateConsultation(consultation.id, {
        symptoms,
        notes,
        status: 'completed',
        results: consultation.results,
      });
      setConsultation(saved);
      queryClient.invalidateQueries({ queryKey: ['consultations'] });
      addToast('success', 'Consultation saved');
    } catch {
      addToast('error', 'Failed to save consultation');
    } finally {
      setSaving(false);
    }
  }, [addToast, consultation, notes, queryClient, symptoms]);

  const handleEnd = useCallback(() => {
    navigate('/dashboard');
  }, [navigate]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <DiagnosisSkeleton />
      </div>
    );
  }

  if (!consultation) {
    return (
      <div className="mx-auto max-w-3xl rounded-xl border border-slate-200 bg-white p-10 text-center shadow-sm">
        <p className="text-sm font-semibold text-slate-600">Consultation not found.</p>
      </div>
    );
  }

  const results = consultation.results;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-normal text-slate-950">Consultation Workspace</h2>
            <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-slate-500">
              <Clock className="h-3.5 w-3.5" />
              Created {new Date(consultation.createdAt).toLocaleString('en-GB', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          </div>
          <span
            className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-bold ${
              consultation.status === 'completed'
                ? 'bg-teal-50 text-teal-800'
                : 'bg-slate-100 text-slate-700'
            }`}
          >
            {consultation.status === 'completed' ? 'Completed' : 'Draft'}
          </span>
        </div>
      </section>

      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" />
        <p className="leading-6">
          MediAssist is advisory. Confirm every diagnosis with clinical examination, diagnostic tests, and professional judgment.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <div className="space-y-5">
          <PatientCard patient={consultation.patient} onChange={() => {}} compact />
          <SymptomInput
            value={symptoms}
            onChange={setSymptoms}
            onSubmit={handleRunAnalysis}
            loading={analyzing}
          />

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <label htmlFor="consultation-notes" className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <FileText className="h-4 w-4 text-teal-700" /> Clinical Notes
            </label>
            <textarea
              id="consultation-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={6}
              placeholder="Assessment, decisions, treatment plan, and follow-up..."
              className="mt-3 w-full resize-none rounded-lg border border-slate-300 p-3 text-sm leading-6 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            />
          </section>
        </div>

        <div className="space-y-5">
          {results && (
            <section className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-slate-500">
                  <Gauge className="h-3.5 w-3.5" /> Confidence
                </p>
                <p className="mt-2 text-lg font-bold capitalize text-slate-950">
                  {results.pipeline_confidence || results.confidence_overall || 'Review'}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">Retrieval</p>
                <p className="mt-2 text-lg font-bold text-slate-950">{results.retrieval_ms ?? '-'} ms</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">LLM</p>
                <p className="mt-2 text-lg font-bold text-slate-950">{results.llm_ms ?? '-'} ms</p>
              </div>
            </section>
          )}

          {results?.warning && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{results.warning}</span>
            </div>
          )}

          {analyzing && <DiagnosisSkeleton />}

          {!analyzing && results && (
            <>
              <DiagnosisList
                diagnoses={results.diagnoses}
                onAccept={handleAccept}
                onReject={handleReject}
              />

              <div className="grid gap-5 lg:grid-cols-2">
                <FollowUpSuggestions
                  suggestions={results.followUps}
                  onAppend={handleAppendFollowUp}
                />
                <RecommendedTests tests={results.recommendedTests} />
              </div>
            </>
          )}
        </div>
      </div>

      <ActionBar
        onSave={handleSave}
        onEnd={handleEnd}
        saving={saving}
        canSave={!!results}
      />
    </div>
  );
}
