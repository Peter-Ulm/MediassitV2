import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from './app-shell';
import { AuthRoute } from './auth-route';
import { LoginPage } from '../pages/login';
import { DashboardPage } from '../pages/dashboard';
import { NewConsultationPage } from '../pages/new-consultation';
import { ConsultationWorkspacePage } from '../pages/consultation-workspace';
import { HistoryPage } from '../pages/history';
import { SettingsPage } from '../pages/settings';
import { HelpPage } from '../pages/help';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <AuthRoute>
        <AppShell />
      </AuthRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'consultation/new', element: <NewConsultationPage /> },
      { path: 'consultation/:id', element: <ConsultationWorkspacePage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'help', element: <HelpPage /> },
    ],
  },
]);
