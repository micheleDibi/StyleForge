import { useState } from 'react';
import { HelpCircle, X } from 'lucide-react';

const COMPONENTS = [
  {
    key: 'relevance',
    label: 'Rilevanza',
    weight: 35,
    hint: 'Posizione del paper nei risultati originali delle fonti (più in alto = più pertinente).',
  },
  {
    key: 'citations',
    label: 'Citazioni',
    weight: 25,
    hint: 'Numero di citazioni, normalizzato in scala logaritmica sul massimo dei risultati.',
  },
  {
    key: 'recency',
    label: 'Recency',
    weight: 15,
    hint: 'Decadimento esponenziale sugli anni: i paper recenti pesano di più.',
  },
  {
    key: 'abstract',
    label: 'Abstract presente',
    weight: 10,
    hint: 'Punteggio pieno se il paper ha un abstract utilizzabile.',
  },
  {
    key: 'venue',
    label: 'Qualità rivista',
    weight: 10,
    hint: 'Massimo delle citazioni di paper pubblicati sulla stessa rivista, normalizzato.',
  },
  {
    key: 'open_access',
    label: 'Open Access',
    weight: 5,
    hint: 'Punteggio pieno se il paper è liberamente accessibile.',
  },
];

const ScoreExplainer = ({ score, breakdown }) => {
  const [open, setOpen] = useState(false);

  if (score == null) return null;

  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);

  const rows = COMPONENTS.map((c) => {
    const value = breakdown?.[c.key];
    const contribution = value != null ? (value * c.weight) : 0;
    return { ...c, value, contribution };
  });
  const total = rows.reduce((s, r) => s + r.contribution, 0);

  return (
    <div className="flex flex-col items-end gap-1 flex-shrink-0 relative">
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-500">Rilevanza</span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
          className="p-0.5 rounded-full text-slate-400 hover:text-slate-600"
          aria-label="Spiegazione del punteggio"
          title="Come viene calcolato il punteggio"
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-orange-400 to-orange-600"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-xs font-semibold text-slate-700">{pct}</div>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            className="absolute right-0 top-8 z-50 w-80 bg-white border border-slate-200 rounded-xl shadow-xl p-4 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-slate-900">
                Punteggio di rilevanza
              </h4>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-0.5 rounded text-slate-400 hover:text-slate-700"
                aria-label="Chiudi"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600 mb-3 leading-relaxed">
              Il punteggio 0-100 pesa sei fattori: più alti i contributi, più il paper è rilevante per la tua ricerca.
            </p>

            <ul className="space-y-2">
              {rows.map((r) => {
                const componentPct = r.value != null ? Math.round(r.value * 100) : 0;
                return (
                  <li key={r.key} className="text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-800">
                        {r.label}
                        <span className="ml-1 text-slate-400 font-normal">(peso {r.weight}%)</span>
                      </span>
                      <span className="text-slate-600 tabular-nums">
                        {componentPct}% × {r.weight}% = <strong className="text-slate-900">{r.contribution.toFixed(1)}</strong>
                      </span>
                    </div>
                    <div className="mt-1 w-full h-1 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-orange-400"
                        style={{ width: `${componentPct}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500 leading-snug">{r.hint}</p>
                  </li>
                );
              })}
            </ul>

            <div className="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between text-xs">
              <span className="text-slate-600">Totale</span>
              <span className="font-semibold text-slate-900">{total.toFixed(1)} / 100</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ScoreExplainer;
