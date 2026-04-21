import { ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { useState } from 'react';

const FilterPanel = ({ filters, onChange, disabled = false }) => {
  const [open, setOpen] = useState(false);

  const update = (key, value) => {
    onChange({ ...filters, [key]: value });
  };

  const activeCount = Object.entries(filters).filter(([k, v]) => {
    if (k === 'open_access_only') return !!v;
    return v !== null && v !== undefined && v !== '';
  }).length;

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl"
      >
        <span className="flex items-center gap-2">
          <Filter className="w-4 h-4" />
          Filtri avanzati
          {activeCount > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-orange-100 text-orange-800 text-xs font-semibold">
              {activeCount}
            </span>
          )}
        </span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Anno minimo</label>
            <input
              type="number"
              value={filters.year_min ?? ''}
              onChange={(e) => update('year_min', e.target.value ? parseInt(e.target.value) : null)}
              disabled={disabled}
              placeholder="es. 2015"
              className="input w-full"
              min="1900"
              max="2100"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Anno massimo</label>
            <input
              type="number"
              value={filters.year_max ?? ''}
              onChange={(e) => update('year_max', e.target.value ? parseInt(e.target.value) : null)}
              disabled={disabled}
              placeholder="es. 2025"
              className="input w-full"
              min="1900"
              max="2100"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Citazioni minime</label>
            <input
              type="number"
              value={filters.min_citations ?? ''}
              onChange={(e) => update('min_citations', e.target.value ? parseInt(e.target.value) : null)}
              disabled={disabled}
              placeholder="es. 10"
              className="input w-full"
              min="0"
            />
          </div>
          <div className="flex items-center gap-2 pt-5">
            <input
              type="checkbox"
              id="oa-only"
              checked={!!filters.open_access_only}
              onChange={(e) => update('open_access_only', e.target.checked)}
              disabled={disabled}
              className="w-4 h-4 rounded border-slate-300 text-orange-500 focus:ring-orange-400"
            />
            <label htmlFor="oa-only" className="text-sm text-slate-700">Solo open access</label>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Rivista / venue contiene</label>
            <input
              type="text"
              value={filters.venue_contains ?? ''}
              onChange={(e) => update('venue_contains', e.target.value || null)}
              disabled={disabled}
              placeholder="es. Nature"
              className="input w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Autore contiene</label>
            <input
              type="text"
              value={filters.author_contains ?? ''}
              onChange={(e) => update('author_contains', e.target.value || null)}
              disabled={disabled}
              placeholder="es. Smith"
              className="input w-full"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default FilterPanel;
