import { Save, FileDown, FlaskConical, XCircle } from 'lucide-react';

interface ActionBarProps {
  onSave: () => void;
  onEnd: () => void;
  saving?: boolean;
  canSave?: boolean;
}

export function ActionBar({ onSave, onEnd, saving, canSave }: ActionBarProps) {
  return (
    <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-xl shadow-slate-900/10 backdrop-blur">
      <button
        onClick={onSave}
        disabled={saving || !canSave}
        className="flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Save className="h-4 w-4" />
        {saving ? 'Saving...' : 'Save'}
      </button>
      <button
        disabled
        className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-slate-400"
        title="Export not available in demo"
      >
        <FileDown className="h-4 w-4" />
        Export
      </button>
      <button
        disabled
        className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-slate-400"
        title="Lab requests not available in demo"
      >
        <FlaskConical className="h-4 w-4" />
        Request Lab
      </button>
      <div className="flex-1" />
      <button
        onClick={onEnd}
        className="flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm font-bold text-red-700 transition-colors hover:bg-red-50"
      >
        <XCircle className="h-4 w-4" />
        End Consultation
      </button>
    </div>
  );
}
