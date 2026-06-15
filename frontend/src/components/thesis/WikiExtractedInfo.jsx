import { useState } from 'react';
import {
  BookMarked, Users, Lightbulb, Layers, GitMerge, HelpCircle, FileText, Tag,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

// Stile per categoria del wiki (chiave = nome cartella backend).
const CATEGORY_META = {
  fonti:    { icon: BookMarked, color: 'text-orange-500',  bg: 'bg-orange-50 border-orange-200' },
  entita:   { icon: Users,      color: 'text-blue-500',    bg: 'bg-blue-50 border-blue-200' },
  concetti: { icon: Lightbulb,  color: 'text-amber-500',   bg: 'bg-amber-50 border-amber-200' },
  temi:     { icon: Layers,     color: 'text-purple-500',  bg: 'bg-purple-50 border-purple-200' },
  sintesi:  { icon: GitMerge,   color: 'text-emerald-500', bg: 'bg-emerald-50 border-emerald-200' },
  domande:  { icon: HelpCircle, color: 'text-rose-500',    bg: 'bg-rose-50 border-rose-200' },
};

const PREVIEW = 5;

const CategoryCard = ({ cat, t }) => {
  const [showAll, setShowAll] = useState(false);
  const meta = CATEGORY_META[cat.key]
    || { icon: FileText, color: 'text-slate-500', bg: 'bg-slate-50 border-slate-200' };
  const Icon = meta.icon;
  const items = showAll ? cat.items : cat.items.slice(0, PREVIEW);

  return (
    <div className={`rounded-2xl border p-4 ${meta.bg}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${meta.color}`} />
          <h4 className="font-semibold text-slate-800">{t(cat.label)}</h4>
        </div>
        <span className="text-xs font-bold text-slate-500">{cat.count}</span>
      </div>
      <ul className="space-y-2.5">
        {items.map((it) => (
          <li key={it.slug} className="text-sm">
            <div className="font-medium text-slate-800">
              {it.title}
              {it.subtype && (
                <span className="ml-2 text-[11px] font-normal text-slate-400">{it.subtype}</span>
              )}
            </div>
            {it.summary && (
              <p className="text-xs text-slate-500 mt-0.5 leading-snug">{it.summary}</p>
            )}
            {it.tag?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {it.tag.slice(0, 4).map((tg, i) => (
                  <span
                    key={`${tg}-${i}`}
                    className="inline-flex items-center gap-0.5 text-[10px] text-slate-500 bg-white/70 border border-slate-200 rounded px-1.5 py-0.5"
                  >
                    <Tag className="w-2.5 h-2.5" />{tg}
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      {cat.items.length > PREVIEW && (
        <button
          onClick={() => setShowAll((s) => !s)}
          className="mt-3 text-xs text-slate-500 hover:text-slate-700 underline"
        >
          {showAll ? t('Mostra meno') : t('Mostra tutti ({{count}})', { count: cat.items.length })}
        </button>
      )}
    </div>
  );
};

/**
 * Vista user-friendly delle informazioni estratte dai documenti caricati.
 * Mostra le pagine del wiki raggruppate per categoria (fonti/entità/concetti/
 * temi/sintesi/domande). Sostituisce il report tecnico di lint per l'utente.
 */
const WikiExtractedInfo = ({ content }) => {
  const { t } = useTranslation();
  if (!content) return null;

  const categories = (content.categories || []).filter((c) => c.count > 0);
  const totalPages = content.totals?.pages || 0;
  const totalSources = content.totals?.sources || 0;

  if (categories.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        {t('Nessuna informazione estratta dai documenti.')}
      </p>
    );
  }

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        {t('{{pages}} pagine di conoscenza estratte da {{sources}} fonti.', { pages: totalPages, sources: totalSources })}
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {categories.map((cat) => <CategoryCard key={cat.key} cat={cat} t={t} />)}
      </div>
    </div>
  );
};

export default WikiExtractedInfo;
