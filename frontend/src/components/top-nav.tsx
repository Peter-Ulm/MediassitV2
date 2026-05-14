import { HelpCircle, LogOut, Settings, ShieldCheck, Stethoscope } from 'lucide-react';
import { useAuth } from '../features/auth/auth-context';
import { useNavigate, useLocation } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';

export function TopNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getPageTitle = () => {
    if (location.pathname === '/dashboard') return 'Dashboard';
    if (location.pathname === '/consultation/new') return 'New Consultation';
    if (location.pathname.startsWith('/consultation/')) return 'Consultation';
    if (location.pathname === '/history') return 'Consultation History';
    if (location.pathname === '/settings') return 'Settings';
    if (location.pathname === '/help') return 'Help & About';
    return 'MediAssist';
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 shadow-sm shadow-slate-200/40 backdrop-blur lg:px-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-700 shadow-sm">
            <Stethoscope className="h-5 w-5 text-white" />
          </div>
          <div className="hidden sm:block">
            <span className="text-lg font-bold tracking-normal text-slate-950">MediAssist</span>
            <p className="-mt-1 text-[11px] font-medium text-slate-500">Tanzania STG decision support</p>
          </div>
        </div>
        <span className="hidden h-6 w-px bg-slate-200 md:block" />
        <h1 className="hidden text-sm font-semibold text-slate-700 md:block">{getPageTitle()}</h1>
      </div>

      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 sm:inline-flex">
          <ShieldCheck className="h-3.5 w-3.5" />
          Clinician review required
        </span>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-100"
            aria-label="User menu"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900">
              <span className="text-sm font-semibold text-white">
                {user?.name?.charAt(0) || 'D'}
              </span>
            </div>
            <div className="hidden text-left sm:block">
              <span className="block text-sm font-semibold text-slate-800">{user?.name}</span>
              <span className="block text-[11px] text-slate-500">Doctor</span>
            </div>
          </button>

          {menuOpen && (
            <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-xl shadow-slate-900/10">
              <button
                onClick={() => { navigate('/settings'); setMenuOpen(false); }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                <Settings className="h-4 w-4" /> Settings
              </button>
              <button
                onClick={() => { navigate('/help'); setMenuOpen(false); }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                <HelpCircle className="h-4 w-4" /> Help & About
              </button>
              <hr className="my-1 border-slate-100" />
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
              >
                <LogOut className="h-4 w-4" /> Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
