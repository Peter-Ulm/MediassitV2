import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './features/auth/auth-context';
import { ToastProvider } from './components/toast';
import { router } from './routes';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

async function bootstrap() {
  // MSW mocks are only used when no real backend is configured.
  // Set VITE_API_BASE_URL in .env.local (e.g. http://localhost:8000/api/v1)
  // to point the frontend at the live FastAPI service. The default empty
  // string means "use mocks" — that keeps the standalone UI demo working.
  const backendUrl = import.meta.env.VITE_API_BASE_URL;
  if (import.meta.env.DEV && !backendUrl) {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
    console.info('[MediAssist] Using MSW mocks (no VITE_API_BASE_URL set)');
  } else if (backendUrl) {
    console.info(`[MediAssist] Using live backend at ${backendUrl}`);
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>
  );
}

bootstrap();
