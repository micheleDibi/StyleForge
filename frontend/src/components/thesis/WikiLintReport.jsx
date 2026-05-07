import { AlertTriangle, BookOpen, GitBranch, Info, Lightbulb, Link2Off, Search, FileQuestion } from 'lucide-react';

const Section = ({ icon: Icon, title, items, color = 'slate', renderItem }) => {
  if (!items || items.length === 0) return null;
  const palette = {
    red: 'bg-red-50 border-red-200 text-red-800',
    amber: 'bg-amber-50 border-amber-200 text-amber-800',
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    slate: 'bg-slate-50 border-slate-200 text-slate-800',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  }[color] || 'bg-slate-50 border-slate-200 text-slate-800';

  return (
    <div className={`rounded-xl border p-4 ${palette}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" />
        <h4 className="font-semibold text-sm">{title}</h4>
        <span className="ml-auto text-[11px] bg-white/60 rounded-full px-2 py-0.5">
          {items.length}
        </span>
      </div>
      <ul className="space-y-1 text-xs">
        {items.slice(0, 8).map((it, i) => (
          <li key={i} className="font-mono break-words">
            {renderItem ? renderItem(it) : String(it)}
          </li>
        ))}
        {items.length > 8 && (
          <li className="text-slate-500 italic">… e altri {items.length - 8}</li>
        )}
      </ul>
    </div>
  );
};

const WikiLintReport = ({ report, summary }) => {
  if (!report) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        Nessun report di lint disponibile.
      </div>
    );
  }

  if (report.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <div className="flex items-center gap-2 mb-1">
          <AlertTriangle className="w-4 h-4" />
          <span className="font-semibold">Errore durante il lint</span>
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
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
          <div className="flex items-center gap-2 mb-1 text-slate-600">
            <Info className="w-4 h-4" />
            <span className="font-semibold">Sintesi del lint</span>
          </div>
          <p className="text-xs leading-relaxed whitespace-pre-wrap">{summary}</p>
        </div>
      )}

      {allClean && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            <span className="font-semibold">Wiki coerente.</span>
          </div>
          <p className="text-xs mt-1">Nessun problema rilevato dal lint. Puoi procedere alla generazione capitoli.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Section
          icon={GitBranch}
          title="Contraddizioni"
          color="red"
          items={contradictions}
          renderItem={(c) => (
            <span>
              <strong>{c.claim}</strong>
              {Array.isArray(c.sources) && c.sources.length > 0 && (
                <em> — fonti: {c.sources.join(', ')}</em>
              )}
            </span>
          )}
        />
        <Section
          icon={Link2Off}
          title="Wikilink rotti"
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
          title="Pagine orfane"
          color="amber"
          items={orphanPages}
        />
        <Section
          icon={Search}
          title="Concetti mancanti"
          color="blue"
          items={missingConcepts}
        />
        <Section
          icon={AlertTriangle}
          title="Frontmatter da correggere"
          color="amber"
          items={fmIssues}
          renderItem={(f) => <span><strong>{f.page}</strong>: {f.issue}</span>}
        />
        <Section
          icon={AlertTriangle}
          title="Gap tematici"
          color="red"
          items={gaps}
        />
        <Section
          icon={Lightbulb}
          title="Suggerimenti di esplorazione"
          color="blue"
          items={suggestions}
        />
        <Section
          icon={Info}
          title="Pagine stantie"
          color="slate"
          items={stalePages}
        />
      </div>
    </div>
  );
};

export default WikiLintReport;
