export interface User {
  id: string;
  name: string;
  role: string;
  email: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface PatientMeta {
  age: number;
  sex: 'male' | 'female' | 'other';
  vitals?: {
    temperature?: number;
    bloodPressure?: string;
    heartRate?: number;
    respiratoryRate?: number;
    weight?: number;
  };
}

export interface EvidenceItem {
  source: string;
  excerpt: string;
  chapter?: string | null;
  section?: string | null;
  relevance_score?: number | null;
}

export interface Diagnosis {
  name: string;
  probability: number;
  evidenceRefs: string[];
  // Extended fields populated by the live backend (Role 3 pipeline).
  // Mocks omit these and the UI falls back gracefully.
  reasoning?: string;
  evidence?: EvidenceItem[];
  accepted?: boolean | null;
}

export interface RecommendedTest {
  test: string;
  rationale: string;
}

export interface DiagnosisResult {
  diagnoses: Diagnosis[];
  followUps: string[];
  recommendedTests: RecommendedTest[];
  confidence_overall?: string;
  pipeline_confidence?: string;
  warning?: string | null;
  retrieval_ms?: number;
  llm_ms?: number;
  total_ms?: number;
  request_id?: string;
  generated_at?: string;
}

export interface Consultation {
  id: string;
  patient: PatientMeta;
  symptoms: string;
  results: DiagnosisResult;
  notes: string;
  status: 'draft' | 'completed';
  createdAt: string;
}

export interface ConsultationSummary {
  id: string;
  patient: PatientMeta;
  summary: string;
  createdAt: string;
  status: 'draft' | 'completed';
}

export interface EvidenceDoc {
  id: string;
  source: string;
  section: string;
  title: string;
  excerpt: string;
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | string;
  llm: {
    provider: string;
    model: string;
    healthy: boolean;
  };
  chroma: {
    collection: string;
    indexed_chunks: number;
    healthy: boolean;
  };
  uptime_seconds: number;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: 'clinician' | 'admin';
  isActive: boolean;
  createdAt: string;
}
