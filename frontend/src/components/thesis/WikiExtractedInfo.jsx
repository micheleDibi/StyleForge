import { useState } from 'react';
import {
  BookMarked, Users, Lightbulb, Layers, GitMerge, HelpCircle, FileText, Tag,
  LayoutGrid, FileStack,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

// Stile per categoria del wiki (chiave = nome cartella backend).
// Classi Tailwind esplicite (niente interpolazione: il purge le richiede intere).
const CATEGORY_META = {
  fonti:    { icon: BookMarked, iconBg: 'bg-orange-100 text-orange-600',  ring: 'border-orange-200',  pill: 'bg-orange-100 text-orange-700' },
  entita:   { icon: Users,      iconBg: 'bg-blue-100 text-blue-600',      ring: 'border-blue-200',    pill: 'bg-blue-100 text-blue-700' },
  concetti: { icon: Lightbulb,  iconBg: 'bg-amber-100 text-amber-600',    ring: 'border-amber-200',   pill: 'bg-amber-100 text-amber-700' },
  temi:     { icon: Layers,     iconBg: 'bg-purple-100 text-purple-600',  ring: 'border-purple-200',  pill: 'bg-purple-100 text-purple-700' },
  sintesi:  { icon: GitMerge,   iconBg: 'bg-emerald-100 text-emerald-600',ring: 'border-emerald-200', pill: 'bg-emerald-100 text-emerald-700' },
  domande:  { icon: HelpCircle, iconBg: 'bg-rose-100 text-rose-600',      ring: 'border-rose-200',    pill: 'bg-rose-100 text-rose-700' },
};

const FALLBACK_META = {
  icon: FileText, iconBg: 'bg-slate-100 text-slate-600', ring: 'border-slate-200', pill: 'bg-slate-100 text-slate-700',
};

const PREVIEW = 5;

const metaFor = (key) => CATEGORY_META[key] || FALLBACK_META;

const CategoryCard = ({ cat, t }) => {
  const [showAll, setShowAll] = useState(false);
  const meta = metaFor(cat.key);
  const Icon = meta.icon;
  const items = showAll ? cat.items : cat.items.slice(0, PREVIEW);

  return (
    <div className={`rounded-2xl border ${meta.ring} bg-white/70 overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${meta.iconBg}`}>
          <Icon className="w-[18px] h-[18px]" />
        </div>
        <h4 className="font-semibold text-slate-800 flex-1">{t(cat.label)}</h4>
        <span className={`text-xs font-bold rounded-full px-2.5 py-1 ${meta.pill}`}>{cat.count}</span>
      </div>

      {/* Items */}
      <ul className="divide-y divide-slate-100">
        {items.map((it) => (
          <li key={it.slug} className="px-4 py-3 hover:bg-slate-50/70 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <span className="font-medium text-slate-800 text-sm leading-snug">{it.title}</span>
              {it.subtype && (
                <span className="flex-shrink-0 text-[10px] uppercase tracking-wide text-slate-400 mt-0.5">{it.subtype}</span>
              )}
            </div>
            {it.summary && (
              <p className="text-xs text-slate-500 mt-1 leading-relaxed line-clamp-2">{it.summary}</p>
            )}
            {it.tag?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {it.tag.slice(0, 5).map((tg, i) => (
                  <span
                    key={`${tg}-${i}`}
                    className="inline-flex items-center gap-0.5 text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-1.5 py-0.5"
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
          className="w-full text-center py-2.5 text-xs font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 border-t border-slate-100 transition-colors"
        >
          {showAll ? t('Mostra meno') : t('Mostra tutti ({{count}})', { count: cat.items.length })}
        </button>
      )}
    </div>
  );
};

/**
 * Vista user-friendly delle informazioni estratte dai documenti caricati.
 * Mostra le pagine del wiki raggruppate per categoria con una barra di
 * riepilogo che fa anche da filtro rapido.
 */
const WikiExtractedInfo = ({ content }) => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState(null); // null = tutte
  if (!content) return null;

  const all = (content.categories || []).filter((c) => c.count > 0);
  const totalPages = content.totals?.pages || 0;
  const totalSources = content.totals?.sources || 0;

  if (all.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        {t('Nessuna informazione estratta dai documenti.')}
      </p>
    );
  }

  const visible = filter ? all.filter((c) => c.key === filter) : all;

  return (
    <div className="space-y-4">
      {/* Barra di riepilogo / filtro rapido */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 mr-1">
          <FileStack className="w-4 h-4 text-slate-400" />
          {t('{{pages}} pagine · {{sources}} fonti', { pages: totalPages, sources: totalSources })}
        </span>
        <button
          onClick={() => setFilter(null)}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
            filter === null ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          {t('Tutte')}
        </button>
        {all.map((cat) => {
          const meta = metaFor(cat.key);
          const Icon = meta.icon;
          const active = filter === cat.key;
          return (
            <button
              key={cat.key}
              onClick={() => setFilter(active ? null : cat.key)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                active ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t(cat.label)}
              <span className={`rounded-full px-1.5 ${active ? 'bg-white/20' : meta.pill}`}>{cat.count}</span>
            </button>
          );
        })}
      </div>

      {/* Card per categoria */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {visible.map((cat) => <CategoryCard key={cat.key} cat={cat} t={t} />)}
      </div>
    </div>
  );
};

export default WikiExtractedInfo;
