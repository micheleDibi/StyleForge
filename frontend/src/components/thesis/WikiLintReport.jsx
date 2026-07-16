import { AlertTriangle, BookOpen, GitBranch, Info, Lightbulb, Link2Off, Search, FileQuestion } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const PALETTE = {
  red:     { card: 'border-red-200',     iconBg: 'bg-red-100 text-red-600',         pill: 'bg-red-100 text-red-700' },
  amber:   { card: 'border-amber-200',   iconBg: 'bg-amber-100 text-amber-600',     pill: 'bg-amber-100 text-amber-700' },
  blue:    { card: 'border-blue-200',    iconBg: 'bg-blue-100 text-blue-600',       pill: 'bg-blue-100 text-blue-700' },
  slate:   { card: 'border-slate-200',   iconBg: 'bg-slate-100 text-slate-600',     pill: 'bg-slate-100 text-slate-700' },
  emerald: { card: 'border-emerald-200', iconBg: 'bg-emerald-100 text-emerald-600', pill: 'bg-emerald-100 text-emerald-700' },
};

const Section = ({ icon, title, items, color = 'slate', renderItem }) => {
  const { t } = useTranslation();
  if (!items || items.length === 0) return null;
  const Icon = icon;
  const p = PALETTE[color] || PALETTE.slate;

  return (
    <div className={`rounded-2xl border ${p.card} bg-white/70 overflow-hidden`}>
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-slate-100">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${p.iconBg}`}>
          <Icon className="w-4 h-4" />
        </div>
        <h4 className="font-semibold text-sm text-slate-800 flex-1">{title}</h4>
        <span className={`text-[11px] font-bold rounded-full px-2 py-0.5 ${p.pill}`}>{items.length}</span>
      </div>
      <ul className="divide-y divide-slate-100">
        {items.slice(0, 8).map((it, i) => (
          <li key={i} className="px-4 py-2.5 text-xs text-slate-600 leading-relaxed break-words">
            {renderItem ? renderItem(it) : String(it)}
          </li>
        ))}
        {items.length > 8 && (
          <li className="px-4 py-2 text-[11px] text-slate-400 italic">{t('… e altri {{n}}', { n: items.length - 8 })}</li>
        )}
      </ul>
    </div>
  );
};

const WikiLintReport = ({ report, summary }) => {
  const { t } = useTranslation();
  if (!report) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        {t('Nessun report di lint disponibile.')}
      </div>
    );
  }

  if (report.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <div className="flex items-center gap-2 mb-1">
          <AlertTriangle className="w-4 h-4" />
          <span className="font-semibold">{t('Errore durante il lint')}</span>
        </div>
        <p className="text-xs font-mono">{report.error}</p>
      </div>
    );
  }

  const orphanPages = report.orphan_pages || [];
  const brokenLinks = report.broken_wikilinks || [];
  const missingConcepts = report.missing_concepts || [];
  const contradictions = report.contradictions || [];
  const stalePages = report.stale_pages || [];
  const fmIssues = report.frontmatter_issues || [];
  const suggestions = report.exploration_suggestions || [];
  const gaps = report.gaps || [];

  const totalIssues = orphanPages.length + brokenLinks.length + contradictions.length + fmIssues.length + gaps.length;
  const allClean = totalIssues === 0;

  return (
    <div className="space-y-4">
      {summary && (
        <div className="rounded-2xl border border-slate-200 bg-white/70 p-4 text-sm text-slate-700">
          <div className="flex items-center gap-2 mb-1 text-slate-600">
            <Info className="w-4 h-4" />
            <span className="font-semibold">{t('Sintesi del lint')}</span>
          </div>
          <p className="text-xs leading-relaxed whitespace-pre-wrap">{summary}</p>
        </div>
      )}

      {allClean && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            <span className="font-semibold">{t('Wiki coerente.')}</span>
          </div>
          <p className="text-xs mt-1">{t('Nessun problema rilevato dal lint. Puoi procedere alla generazione capitoli.')}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section
          icon={GitBranch}
          title={t('Contraddizioni')}
          color="red"
          items={contradictions}
          renderItem={(c) => (
            <span>
              <strong>{c.claim}</strong>
              {Array.isArray(c.sources) && c.sources.length > 0 && (
                <em> {t('— fonti: {{sources}}', { sources: c.sources.join(', ') })}</em>
              )}
            </span>
          )}
        />
        <Section
          icon={Link2Off}
          title={t('Wikilink rotti')}
          color="amber"
          items={brokenLinks}
          renderItem={(b) => (
            <span>
              <strong>{b.in_page}</strong> → <code>[[{b.target}]]</code>
            </span>
          )}
        />
        <Section
          icon={FileQuestion}
          title={t('Pagine orfane')}
          color="amber"
          items={orphanPages}
        />
        <Section
          icon={Search}
          title={t('Concetti mancanti')}
          color="blue"
          items={missingConcepts}
        />
        <Section
          icon={AlertTriangle}
          title={t('Frontmatter da correggere')}
          color="amber"
          items={fmIssues}
          renderItem={(f) => <span><strong>{f.page}</strong>: {f.issue}</span>}
        />
        <Section
          icon={AlertTriangle}
          title={t('Gap tematici')}
          color="red"
          items={gaps}
        />
        <Section
          icon={Lightbulb}
          title={t('Suggerimenti di esplorazione')}
          color="blue"
          items={suggestions}
        />
        <Section
          icon={Info}
          title={t('Pagine stantie')}
          color="slate"
          items={stalePages}
        />
      </div>
    </div>
  );
};

export default WikiLintReport;
