import { BookOpen, Cpu, Info, Shield } from 'lucide-react';

export function HelpPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-950">Help & About</h2>
        <p className="mt-1 text-sm text-slate-500">Clinical workflow, evidence grounding, and safety posture</p>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Cpu className="h-5 w-5 text-teal-700" />
            <h3 className="font-bold text-slate-950">MediAssist</h3>
          </div>
          <p className="text-sm leading-6 text-slate-600">
            MediAssist is a clinical decision support system for Tanzanian healthcare settings. It combines guideline retrieval with structured AI reasoning to produce ranked diagnostic suggestions.
          </p>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-teal-700" />
            <h3 className="font-bold text-slate-950">Evidence Grounding</h3>
          </div>
          <ol className="list-inside list-decimal space-y-2 text-sm leading-6 text-slate-600">
            <li>Symptoms are converted into a retrieval query.</li>
            <li>Relevant Tanzania STG passages are selected from the local vector store.</li>
            <li>The diagnosis response is validated and shown with evidence.</li>
          </ol>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Shield className="h-5 w-5 text-teal-700" />
            <h3 className="font-bold text-slate-950">Human-in-the-Loop</h3>
          </div>
          <p className="text-sm leading-6 text-slate-600">
            The doctor reviews, accepts, rejects, and documents decisions. The system provides support, not autonomous diagnosis or treatment authority.
          </p>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Info className="h-5 w-5 text-teal-700" />
            <h3 className="font-bold text-slate-950">Demo Notes</h3>
          </div>
          <ul className="list-inside list-disc space-y-2 text-sm leading-6 text-slate-600">
            <li>Use the demo account for presentation access.</li>
            <li>Backend health depends on the local Python environment and model server.</li>
            <li>Consultations are stored in the running backend process for this demo.</li>
          </ul>
        </section>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm font-semibold leading-6 text-amber-900">
          Disclaimer: MediAssist is for academic demonstration and clinical decision support only. Do not use it for real patient care without validation, governance, and clinician oversight.
        </p>
      </div>
    </div>
  );
}
