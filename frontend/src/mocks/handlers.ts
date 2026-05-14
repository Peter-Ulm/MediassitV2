import { http, HttpResponse, delay } from 'msw';
import evidenceData from './data/evidence.json';
import consultationsData from './data/consultations.json';
import type { Consultation, Diagnosis, DiagnosisResult, PatientMeta } from '../api/types';

const DEMO_EMAIL = 'dr.demo@mediassist.test';
const DEMO_PASSWORD = 'DemoPass123';
const DEMO_TOKEN = 'mock-jwt-token-dr-demo-2026';

function generateDiagnoses(symptoms: string, patient: PatientMeta): DiagnosisResult {
  const lower = symptoms.toLowerCase();
  const isPediatric = patient.age < 12;
  const hasFever = lower.includes('fever') || lower.includes('pyrexia') || lower.includes('hot');
  const hasCough = lower.includes('cough') || lower.includes('sputum') || lower.includes('respirat');
  const hasGi = lower.includes('diarrhea') || lower.includes('vomit') || lower.includes('abdomi') || lower.includes('gastro');

  if (hasFever && !hasCough) {
    const diagnoses: Diagnosis[] = [
      { name: 'Malaria', probability: isPediatric ? 0.55 : 0.75, evidenceRefs: ['stg:malaria:sec3'] },
      { name: 'Typhoid Fever', probability: isPediatric ? 0.25 : 0.15, evidenceRefs: ['stg:typhoid:sec2'] },
      { name: 'Viral infection', probability: isPediatric ? 0.20 : 0.10, evidenceRefs: ['stg:viral:sec1'] },
    ];
    if (isPediatric) {
      diagnoses[0].evidenceRefs.push('stg:pediatric-fever:sec1');
    }
    return {
      diagnoses,
      followUps: [
        'Has the patient travelled recently?',
        'Is there a cough?',
        ...(hasGi ? [] : ['Any gastrointestinal symptoms?']),
      ],
      recommendedTests: [
        { test: 'mRDT', rationale: 'STG recommends mRDT for suspected malaria' },
        ...(isPediatric ? [{ test: 'Urine dipstick', rationale: 'To rule out UTI in febrile child' }] : []),
      ],
    };
  }

  if (hasCough) {
    return {
      diagnoses: [
        { name: 'Community-Acquired Pneumonia', probability: 0.50, evidenceRefs: ['stg:pneumonia:sec2'] },
        { name: 'Acute URTI', probability: 0.35, evidenceRefs: ['stg:urti:sec1'] },
        { name: 'Viral bronchitis', probability: 0.15, evidenceRefs: ['stg:viral:sec1'] },
      ],
      followUps: [
        'Is the sputum purulent or blood-stained?',
        'Is there chest pain?',
        'Any history of COPD or asthma?',
      ],
      recommendedTests: [
        { test: 'Chest X-ray', rationale: 'To confirm pneumonia and assess severity' },
        { test: 'Pulse oximetry', rationale: 'To assess oxygenation' },
      ],
    };
  }

  return {
    diagnoses: [
      { name: 'Viral infection', probability: 0.60, evidenceRefs: ['stg:viral:sec1'] },
      { name: 'Malaria', probability: 0.25, evidenceRefs: ['stg:malaria:sec3'] },
      { name: 'Typhoid Fever', probability: 0.15, evidenceRefs: ['stg:typhoid:sec2'] },
    ],
    followUps: ['How long have the symptoms persisted?', 'Is there a fever?', 'Any recent travel?'],
    recommendedTests: [{ test: 'mRDT', rationale: 'To rule out malaria in endemic area' }],
  };
}

let nextConsultId = 4;

export const handlers = [
  http.get('/health', async () => {
    await delay(150);
    return HttpResponse.json({
      status: 'ok',
      llm: { provider: 'mock', model: 'demo-rules', healthy: true },
      chroma: { collection: 'mediassist_stg', indexed_chunks: 3724, healthy: true },
      uptime_seconds: 3600,
    });
  }),

  http.post('/auth/login', async ({ request }) => {
    await delay(400);
    const body = (await request.json()) as { username: string; password: string };
    if (body.username === DEMO_EMAIL && body.password === DEMO_PASSWORD) {
      return HttpResponse.json({
        token: DEMO_TOKEN,
        user: { id: 'user-demo-001', name: 'Dr. Demo', role: 'doctor', email: DEMO_EMAIL },
      });
    }
    return HttpResponse.json({ error: 'Invalid credentials' }, { status: 401 });
  }),

  http.get('/consultations', async ({ request }) => {
    await delay(200);
    const auth = request.headers.get('Authorization');
    if (auth !== `Bearer ${DEMO_TOKEN}`) {
      return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const stored = localStorage.getItem('mediassist_consultations');
    const all = stored ? JSON.parse(stored) : consultationsData.consultations;
    return HttpResponse.json(
      all.map((c: { id: string; patient: PatientMeta; symptoms: string; status: string; createdAt: string }) => ({
        id: c.id,
        patient: c.patient,
        summary: c.symptoms.slice(0, 80),
        status: c.status,
        createdAt: c.createdAt,
      }))
    );
  }),

  http.get('/consultations/:id', async ({ params, request }) => {
    await delay(200);
    const auth = request.headers.get('Authorization');
    if (auth !== `Bearer ${DEMO_TOKEN}`) {
      return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const stored = localStorage.getItem('mediassist_consultations');
    const all = stored ? JSON.parse(stored) : consultationsData.consultations;
    const consultation = all.find((c: { id: string }) => c.id === params.id);
    if (!consultation) {
      return HttpResponse.json({ error: 'Not found' }, { status: 404 });
    }
    return HttpResponse.json(consultation);
  }),

  http.patch('/consultations/:id', async ({ params, request }) => {
    await delay(250);
    const auth = request.headers.get('Authorization');
    if (auth !== `Bearer ${DEMO_TOKEN}`) {
      return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const updates = (await request.json()) as Partial<Consultation>;
    const stored = localStorage.getItem('mediassist_consultations');
    const all = stored ? JSON.parse(stored) : [...consultationsData.consultations];
    const idx = all.findIndex((c: Consultation) => c.id === params.id);
    if (idx < 0) {
      return HttpResponse.json({ error: 'Not found' }, { status: 404 });
    }
    all[idx] = { ...all[idx], ...updates };
    localStorage.setItem('mediassist_consultations', JSON.stringify(all));
    return HttpResponse.json(all[idx]);
  }),

  http.post('/consultations', async ({ request }) => {
    await delay(300);
    const auth = request.headers.get('Authorization');
    if (auth !== `Bearer ${DEMO_TOKEN}`) {
      return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const body = (await request.json()) as { patient: PatientMeta; symptoms: string };
    const results = generateDiagnoses(body.symptoms, body.patient);
    const consultation = {
      id: `consult-${String(nextConsultId++).padStart(3, '0')}`,
      patient: body.patient,
      symptoms: body.symptoms,
      results,
      notes: '',
      status: 'draft',
      createdAt: new Date().toISOString(),
    };
    const stored = localStorage.getItem('mediassist_consultations');
    const all = stored ? JSON.parse(stored) : [...consultationsData.consultations];
    all.unshift(consultation);
    localStorage.setItem('mediassist_consultations', JSON.stringify(all));
    return HttpResponse.json(consultation);
  }),

  http.post('/diagnosis/retrieve', async () => {
    await delay(600);
    return HttpResponse.json({
      retrievedDocs: evidenceData.evidence.slice(0, 3),
      embeddingsMeta: { model: 'gte-small', latency: 120 },
    });
  }),

  http.post('/diagnosis/generate', async ({ request }) => {
    await delay(1200);
    const body = (await request.json()) as { symptoms: string; patientMeta?: PatientMeta };
    const results = generateDiagnoses(body.symptoms, body.patientMeta || { age: 30, sex: 'male' });
    return HttpResponse.json(results);
  }),
];
