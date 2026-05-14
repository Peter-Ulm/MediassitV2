import { useAuth } from '../features/auth/auth-context';
import { User, Bell, Eye, Globe } from 'lucide-react';
import { useState } from 'react';

export function SettingsPage() {
  const { user } = useAuth();
  const [showEvidence, setShowEvidence] = useState(true);
  const [language, setLanguage] = useState('en');

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-950">Settings</h2>
        <p className="mt-1 text-sm text-slate-500">Account and consultation preferences</p>
      </div>

      <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-3 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900">
            <User className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">{user?.name}</p>
            <p className="text-xs text-slate-500">{user?.email}</p>
          </div>
          <span className="ml-auto rounded-full bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-800">
            Demo
          </span>
        </div>
      </div>

      <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-3">
            <Eye className="h-5 w-5 text-teal-700" />
            <div>
              <p className="text-sm font-bold text-slate-900">Show evidence by default</p>
              <p className="text-xs text-slate-500">Expand evidence panels automatically</p>
            </div>
          </div>
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className={`relative h-5 w-10 rounded-full transition-colors ${
              showEvidence ? 'bg-teal-700' : 'bg-slate-300'
            }`}
            role="switch"
            aria-checked={showEvidence}
          >
            <span
              className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                showEvidence ? 'translate-x-5' : ''
              }`}
            />
          </button>
        </div>

        <div className="flex items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-3">
            <Globe className="h-5 w-5 text-teal-700" />
            <div>
              <p className="text-sm font-bold text-slate-900">Language</p>
              <p className="text-xs text-slate-500">Interface language</p>
            </div>
          </div>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          >
            <option value="en">English</option>
            <option value="sw">Swahili</option>
          </select>
        </div>

        <div className="flex items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-3">
            <Bell className="h-5 w-5 text-teal-700" />
            <div>
              <p className="text-sm font-bold text-slate-900">Notifications</p>
              <p className="text-xs text-slate-500">Not available in demo</p>
            </div>
          </div>
          <span className="text-xs font-semibold text-slate-400">Coming soon</span>
        </div>
      </div>
    </div>
  );
}
