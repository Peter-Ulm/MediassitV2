import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Clock,
  HelpCircle,
  LayoutDashboard,
  PlusCircle,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useState } from 'react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/consultation/new', icon: PlusCircle, label: 'New Consultation' },
  { to: '/history', icon: Clock, label: 'History' },
  { to: '/settings', icon: Settings, label: 'Settings' },
  { to: '/help', icon: HelpCircle, label: 'Help' },
];

export function SideNav() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`${
        collapsed ? 'w-[72px]' : 'w-64'
      } hidden lg:flex flex-col border-r border-slate-200/80 bg-white/90 backdrop-blur transition-all duration-200`}
    >
      <nav className="flex-1 py-5">
        <ul className="space-y-1.5 px-3">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-teal-50 text-teal-800 shadow-[inset_3px_0_0_#0f766e]'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                  }`
                }
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {!collapsed && (
        <div className="mx-3 mb-3 rounded-lg border border-teal-100 bg-teal-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-teal-900">
            <ShieldCheck className="h-4 w-4" />
            Evidence-first CDSS
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs text-teal-800">
            <Activity className="h-3.5 w-3.5" />
            Local STG knowledge base
          </div>
        </div>
      )}

      <div className="border-t border-slate-100 p-3">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex w-full items-center justify-center rounded-lg py-2 text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-700"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
