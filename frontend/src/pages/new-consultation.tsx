import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import type { PatientMeta } from '../api/types';
import { SymptomInput } from '../components/symptom-input';
import { PatientCard } from '../components/patient-card';
import { useToast } from '../components/toast';
import { BookOpen, CheckCircle2, ShieldCheck } from 'lucide-react';

export function NewConsultationPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [patient, setPatient] = useState<PatientMeta>({ age: 30, sex: 'male' });
  const [symptoms, setSymptoms] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!symptoms.trim()) return;
    setSubmitting(true);
    try {
      const consultation = await api.createConsultation(patient, symptoms.trim());
      addToast('success', 'Consultation created. Review the evidence and ranked diagnosis.');
      navigate(`/consultation/${consultation.id}`);
    } catch {
      addToast('error', 'Failed to create consultation. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800">
              <BookOpen className="h-3.5 w-3.5" />
              Tanzania STG-grounded workflow
            </div>
            <h2 className="text-2xl font-bold tracking-normal text-slate-950">New Consultation</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Build a clear clinical query, retrieve guideline evidence, and generate a differential diagnosis for review.
            </p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900">
            Decision support only. Clinician judgment remains final.
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className="space-y-5">
          <PatientCard patient={patient} onChange={setPatient} />
          <SymptomInput
            value={symptoms}
            onChange={setSymptoms}
            onSubmit={handleSubmit}
            loading={submitting}
          />
        </div>

        <aside className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <ShieldCheck className="h-4 w-4 text-teal-700" />
              Review Checklist
            </h3>
            <div className="mt-4 space-y-3">
              {[
                'Demographics recorded',
                'Key symptoms and duration captured',
                'Vitals added when available',
                'Evidence reviewed before action',
              ].map((item, index) => (
                <div key={item} className="flex items-center gap-2 text-sm text-slate-700">
                  <CheckCircle2 className={`h-4 w-4 ${index < 2 ? 'text-teal-700' : 'text-slate-300'}`} />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-950 p-4 text-white shadow-sm">
            <p className="text-sm font-bold">Clinical Safety</p>
            <p className="mt-2 text-xs leading-5 text-slate-300">
              AI suggestions are advisory. Confirm findings with examination, tests, and local clinical protocols.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
