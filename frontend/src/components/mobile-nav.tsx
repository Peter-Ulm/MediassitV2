import { LayoutDashboard, PlusCircle, Clock } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const bottomNavItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Home' },
  { to: '/consultation/new', icon: PlusCircle, label: 'New' },
  { to: '/history', icon: Clock, label: 'History' },
];

export function MobileNav() {
  return (
    <nav className="safe-area-bottom fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200 bg-white/95 shadow-[0_-8px_30px_rgba(15,23,42,0.08)] backdrop-blur lg:hidden">
      <ul className="flex items-center justify-around py-2">
        {bottomNavItems.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `flex min-w-16 flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  isActive ? 'bg-teal-50 text-teal-800' : 'text-slate-500'
                }`
              }
            >
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
