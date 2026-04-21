import { Info, Lightbulb, Tag, AlertTriangle } from 'lucide-react';

const PaperSummary = ({ summary }) => {
  if (!summary) return null;

  return (
    <div className="mt-4 space-y-4 rounded-xl border border-orange-200 bg-orange-50/50 p-4">
      {summary.limited_input && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Abstract non disponibile: il riassunto si basa solo sui metadati ed è necessariamente generico.
          </span>
        </div>
      )}

      <section>
        <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-1">
          <Info className="w-4 h-4 text-orange-600" />
          Riassunto breve
        </h4>
        <p className="text-sm text-slate-700 leading-relaxed">{summary.summary_short || '—'}</p>
      </section>

      <section>
        <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-1">
          <Lightbulb className="w-4 h-4 text-orange-600" />
          Riassunto tecnico
        </h4>
        <p className="text-sm text-slate-700 leading-relaxed">{summary.summary_technical || '—'}</p>
      </section>

      {summary.keywords?.length > 0 && (
        <section>
          <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-2">
            <Tag className="w-4 h-4 text-orange-600" />
            Parole chiave
          </h4>
          <div className="flex flex-wrap gap-2">
            {summary.keywords.map((k, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-1 rounded-full bg-white border border-orange-200 text-orange-800 text-xs font-medium"
              >
                {k}
              </span>
            ))}
          </div>
        </section>
      )}

      {summary.limits?.length > 0 && (
        <section>
          <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-2">
            <AlertTriangle className="w-4 h-4 text-orange-600" />
            Limiti dello studio
          </h4>
          <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
            {summary.limits.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default PaperSummary;
