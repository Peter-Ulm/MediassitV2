import evidenceData from '../mocks/data/evidence.json';
import type { EvidenceItem } from '../api/types';
import { BookOpen, ExternalLink } from 'lucide-react';

interface EvidencePanelProps {
  refs?: string[];
  items?: EvidenceItem[];
}

export function EvidencePanel({ refs = [], items = [] }: EvidencePanelProps) {
  const liveDocs = items.map((item, index) => ({
    id: `${item.source}-${index}`,
    title: item.chapter || item.source,
    section: item.section || item.chapter || 'STG evidence',
    source: item.source,
    excerpt: item.excerpt,
    relevance: item.relevance_score,
  }));
  const mockDocs = evidenceData.evidence
    .filter((e) => refs.includes(e.id))
    .map((item) => ({ ...item, relevance: undefined }));
  const docs = liveDocs.length > 0 ? liveDocs : mockDocs;

  if (docs.length === 0) {
    return <p className="text-xs font-medium text-slate-500">No evidence documents found for this diagnosis.</p>;
  }

  return (
    <div className="space-y-3">
      {docs.map((doc) => (
        <div key={doc.id} className="border-l-2 border-teal-500 pl-3">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5 flex-shrink-0 text-teal-700" />
              <span className="truncate text-xs font-bold text-slate-800">{doc.title}</span>
            </div>
            <span className="text-xs font-medium text-slate-500">{doc.section}</span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{doc.excerpt}</p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="inline-flex items-center gap-1 font-bold text-teal-800">
              <ExternalLink className="h-3 w-3" />
              {doc.source}
            </span>
            {typeof doc.relevance === 'number' && (
              <span className="font-semibold text-slate-400">relevance {doc.relevance.toFixed(2)}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
