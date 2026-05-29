import type {
  AdminUser,
  AuthResponse,
  Consultation,
  ConsultationSummary,
  DiagnosisResult,
  HealthStatus,
  PatientMeta,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('mediassist_token');
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('mediassist_token');
    localStorage.removeItem('mediassist_user');
    if (window.location.pathname !== '/login') {
      window.location.assign('/login');
    }
    throw new Error('Session expired — please log in again.');
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  health: () => request<HealthStatus>('/health'),

  login: (username: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  createConsultation: (patient: PatientMeta, symptoms: string, meta?: Record<string, unknown>) =>
    request<Consultation>('/consultations', {
      method: 'POST',
      body: JSON.stringify({ patient, symptoms, meta }),
    }),

  getConsultation: (id: string) =>
    request<Consultation>(`/consultations/${id}`),

  updateConsultation: (
    id: string,
    updates: Partial<Pick<Consultation, 'symptoms' | 'results' | 'notes' | 'status'>>
  ) =>
    request<Consultation>(`/consultations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  listConsultations: () =>
    request<ConsultationSummary[]>('/consultations'),

  retrieveDiagnosis: (symptoms: string, patientMeta: PatientMeta) =>
    request<{ retrievedDocs: unknown[]; embeddingsMeta: unknown }>('/diagnosis/retrieve', {
      method: 'POST',
      body: JSON.stringify({ symptoms, patientMeta }),
    }),

  generateDiagnosis: (symptoms: string, patientMeta: PatientMeta) =>
    request<DiagnosisResult>('/diagnosis/generate', {
      method: 'POST',
      body: JSON.stringify({ symptoms, patientMeta }),
    }),

  listUsers: () => request<AdminUser[]>('/admin/users'),

  createUser: (payload: { email: string; name: string; password: string; role: 'clinician' | 'admin' }) =>
    request<AdminUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload) }),

  updateUser: (id: string, updates: { isActive?: boolean; role?: 'clinician' | 'admin' }) =>
    request<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(updates) }),

  resetUserPassword: (id: string, password: string) =>
    request<{ ok: boolean }>(`/admin/users/${id}/reset-password`, {
      method: 'POST', body: JSON.stringify({ password }),
    }),
};
