import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/auth-context';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
  Stethoscope,
} from 'lucide-react';

const DEMO_EMAIL = 'dr.demo@mediassist.test';
const DEMO_PASSWORD = 'DemoPass123';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch {
      setError('Invalid email or password. Use demo credentials to sign in.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    setError('');
    setLoading(true);
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD);
      navigate('/dashboard');
    } catch {
      setError('Demo login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#f8fafc_0%,#eef7f6_48%,#f7f5ff_100%)] p-4 text-slate-950">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] w-full max-w-6xl items-center gap-8 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="hidden lg:block">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-700 shadow-lg shadow-teal-900/15">
              <Stethoscope className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-normal text-slate-950">MediAssist</h1>
              <p className="text-sm font-medium text-slate-500">Clinical decision support for Tanzanian care teams</p>
            </div>
          </div>

          <div className="max-w-xl">
            <h2 className="text-4xl font-bold leading-tight tracking-normal text-slate-950">
              Evidence-grounded diagnosis support that keeps the doctor in control.
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600">
              Enter symptoms, retrieve Tanzania Standard Treatment Guideline evidence, and review a ranked differential with transparent reasoning.
            </p>
          </div>

          <div className="mt-8 grid max-w-xl grid-cols-3 gap-3">
            {[
              { icon: BookOpen, label: 'STG evidence', value: '3,724 chunks' },
              { icon: ShieldCheck, label: 'Safety posture', value: 'Human review' },
              { icon: LockKeyhole, label: 'Demo mode', value: 'Local first' },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-white/70 bg-white/70 p-4 shadow-sm shadow-slate-200/70 backdrop-blur">
                <item.icon className="h-5 w-5 text-teal-700" />
                <p className="mt-3 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">{item.label}</p>
                <p className="mt-1 text-sm font-bold text-slate-950">{item.value}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 max-w-xl rounded-lg border border-slate-200 bg-white p-4 shadow-xl shadow-slate-900/10">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <p className="text-sm font-bold text-slate-900">Live consultation preview</p>
                <p className="text-xs text-slate-500">Ranked output with evidence traceability</p>
              </div>
              <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">Ready</span>
            </div>
            <div className="mt-4 space-y-3">
              {[
                ['Malaria', 'High', '75%'],
                ['Typhoid fever', 'Moderate', '15%'],
                ['Viral illness', 'Low', '10%'],
              ].map(([name, label, value]) => (
                <div key={name} className="flex items-center gap-3">
                  <CheckCircle2 className="h-4 w-4 text-teal-700" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm font-semibold text-slate-800">{name}</span>
                      <span className="text-xs font-bold text-slate-600">{value}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-slate-100">
                      <div className="h-1.5 rounded-full bg-teal-600" style={{ width: value }} />
                    </div>
                  </div>
                  <span className="w-16 text-right text-xs font-semibold text-slate-500">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto w-full max-w-md">
          <div className="mb-6 text-center lg:hidden">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-teal-700 shadow-lg shadow-teal-900/15">
              <Stethoscope className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-950">MediAssist</h1>
            <p className="mt-1 text-sm text-slate-500">Clinical decision support powered by evidence</p>
          </div>

          <div className="rounded-xl border border-white/70 bg-white/95 p-6 shadow-2xl shadow-slate-900/10 backdrop-blur">
            <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-center text-xs font-semibold text-amber-900">
                Demo environment. Not for real clinical decisions.
              </p>
            </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-semibold text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 transition-shadow placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                placeholder="doctor@example.com"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-semibold text-slate-700">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-sm text-slate-900 transition-shadow placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                  placeholder="Enter password"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-teal-700 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 font-medium text-slate-400">or</span>
            </div>
          </div>

          <button
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full rounded-lg border border-teal-200 bg-teal-50 py-2.5 text-sm font-bold text-teal-800 transition-colors hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Continue as Demo Doctor
          </button>

          <div className="mt-4 text-center">
            <p className="text-xs text-slate-500">
              Demo: {DEMO_EMAIL} / {DEMO_PASSWORD}
            </p>
          </div>
        </div>

          <p className="mt-5 text-center text-xs leading-5 text-slate-500">
            MediAssist provides decision support only. A qualified clinician must confirm every diagnosis and treatment decision.
          </p>
        </section>
      </div>
    </div>
  );
}
