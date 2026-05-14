import { Activity, Heart, Thermometer, User } from 'lucide-react';
import type { PatientMeta } from '../api/types';

interface PatientCardProps {
  patient: PatientMeta;
  onChange: (patient: PatientMeta) => void;
  compact?: boolean;
}

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition-shadow placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100';

export function PatientCard({ patient, onChange, compact }: PatientCardProps) {
  const update = (patch: Partial<PatientMeta>) => onChange({ ...patient, ...patch });
  const updateVitals = (patch: Partial<NonNullable<PatientMeta['vitals']>>) =>
    update({ vitals: { ...patient.vitals, ...patch } });

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
        <span className="inline-flex items-center gap-1.5 font-semibold text-slate-800">
          <User className="h-4 w-4 text-teal-700" />
          {patient.age}y, {patient.sex}
        </span>
        {patient.vitals?.temperature && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">
            <Thermometer className="h-3.5 w-3.5" />
            {patient.vitals.temperature}°C
          </span>
        )}
        {patient.vitals?.heartRate && (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
            <Heart className="h-3.5 w-3.5" />
            {patient.vitals.heartRate} bpm
          </span>
        )}
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <User className="h-4 w-4 text-teal-700" /> Patient Profile
          </h3>
          <p className="mt-1 text-xs text-slate-500">Demographics and vital signs</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="mb-1 block text-xs font-bold text-slate-500">Age</label>
          <input
            type="number"
            min={0}
            max={120}
            value={patient.age}
            onChange={(e) => update({ age: Number(e.target.value) })}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-bold text-slate-500">Sex</label>
          <select
            value={patient.sex}
            onChange={(e) => update({ sex: e.target.value as PatientMeta['sex'] })}
            className={inputClass}
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="mb-1 flex items-center gap-1 text-xs font-bold text-slate-500">
            <Thermometer className="h-3.5 w-3.5" /> Temperature
          </label>
          <input
            type="number"
            step={0.1}
            value={patient.vitals?.temperature ?? ''}
            onChange={(e) => updateVitals({ temperature: Number(e.target.value) || undefined })}
            placeholder="37.0"
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 flex items-center gap-1 text-xs font-bold text-slate-500">
            <Heart className="h-3.5 w-3.5" /> Heart rate
          </label>
          <input
            type="number"
            value={patient.vitals?.heartRate ?? ''}
            onChange={(e) => updateVitals({ heartRate: Number(e.target.value) || undefined })}
            placeholder="80"
            className={inputClass}
          />
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block text-xs font-bold text-slate-500">Blood pressure</label>
          <input
            type="text"
            value={patient.vitals?.bloodPressure ?? ''}
            onChange={(e) => updateVitals({ bloodPressure: e.target.value || undefined })}
            placeholder="120/80"
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 flex items-center gap-1 text-xs font-bold text-slate-500">
            <Activity className="h-3.5 w-3.5" /> Respiratory rate
          </label>
          <input
            type="number"
            value={patient.vitals?.respiratoryRate ?? ''}
            onChange={(e) => updateVitals({ respiratoryRate: Number(e.target.value) || undefined })}
            placeholder="18"
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-bold text-slate-500">Weight</label>
          <input
            type="number"
            step={0.1}
            value={patient.vitals?.weight ?? ''}
            onChange={(e) => updateVitals({ weight: Number(e.target.value) || undefined })}
            placeholder="70"
            className={inputClass}
          />
        </div>
      </div>
    </section>
  );
}
