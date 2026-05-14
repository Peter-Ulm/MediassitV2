import { Outlet } from 'react-router-dom';
import { TopNav } from '../components/top-nav';
import { SideNav } from '../components/side-nav';
import { MobileNav } from '../components/mobile-nav';

export function AppShell() {
  return (
    <div className="h-screen flex flex-col bg-[linear-gradient(180deg,#f8fafc_0%,#eef6f6_100%)]">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <SideNav />
        <main className="clinical-scrollbar flex-1 overflow-y-auto px-4 py-5 pb-24 sm:px-6 lg:px-8 lg:py-7 lg:pb-8">
          <Outlet />
        </main>
      </div>
      <MobileNav />
    </div>
  );
}
