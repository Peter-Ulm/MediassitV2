import { Navigate } from 'react-router-dom';
import { useAuth } from '../features/auth/auth-context';
import type { ReactNode } from 'react';

export function AuthRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
