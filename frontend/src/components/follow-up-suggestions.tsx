import { MessageCirclePlus } from 'lucide-react';

interface FollowUpSuggestionsProps {
  suggestions: string[];
  onAppend: (question: string) => void;
}

export function FollowUpSuggestions({ suggestions, onAppend }: FollowUpSuggestionsProps) {
  if (suggestions.length === 0) return null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-bold text-slate-950">Suggested Follow-up Questions</h3>
      <div className="mt-3 space-y-2">
        {suggestions.map((q, i) => (
          <button
            key={i}
            onClick={() => onAppend(q)}
            className="group flex w-full items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left text-sm text-slate-700 transition-colors hover:border-teal-300 hover:bg-teal-50"
          >
            <MessageCirclePlus className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400 group-hover:text-teal-700" />
            <span className="leading-5">{q}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
