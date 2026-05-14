import { Send, Sparkles, X } from 'lucide-react';

interface SymptomInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading?: boolean;
}

const examples = ['Fever with chills', 'Cough and chest pain', 'Headache with vomiting'];

export function SymptomInput({ value, onChange, onSubmit, loading }: SymptomInputProps) {
  const applyExample = (example: string) => {
    onChange(value.trim() ? `${value.trim()}; ${example}` : example);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!loading && value.trim()) onSubmit();
      }}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <label htmlFor="symptom-input" className="block text-sm font-bold text-slate-900">
            Clinical Presentation
          </label>
          <p className="mt-1 text-xs text-slate-500">Free-text symptoms, duration, risk factors, and relevant negatives</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => applyExample(example)}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600 transition-colors hover:border-teal-200 hover:bg-teal-50 hover:text-teal-800 disabled:opacity-50"
            >
              <Sparkles className="h-3 w-3" />
              {example}
            </button>
          ))}
        </div>
      </div>

      <textarea
        id="symptom-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Example: fever for 3 days with chills, headache, reduced appetite, no cough..."
        className="min-h-32 w-full resize-none rounded-lg border border-slate-300 bg-white p-3 text-sm leading-6 text-slate-900 shadow-sm transition-shadow placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        rows={5}
        disabled={loading}
        aria-label="Symptom input"
      />

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {loading ? 'Analyzing...' : 'Run MediAssist'}
        </button>
        <button
          type="button"
          onClick={() => onChange('')}
          disabled={loading || !value}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <X className="h-4 w-4" />
          Clear
        </button>
        <span className="text-xs font-medium text-slate-400 sm:ml-auto">{value.trim().length} characters</span>
      </div>
    </form>
  );
}
