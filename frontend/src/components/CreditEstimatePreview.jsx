import { useState, useEffect, useRef } from 'react';
import { Coins, Loader } from 'lucide-react';
import { estimateCredits } from '../services/api';
import { useAuth } from '../context/AuthContext';

/**
 * Preview crediti. Accetta:
 * - operationType + params (singola operazione)
 * - operations: [{ type, params, label }] (multiple operazioni, somma totale)
 */
const CreditEstimatePreview = ({ operationType, params, operations }) => {
  const { isAdmin, credits } = useAuth();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  // Normalizza: singola operazione -> array
  const ops = operations || [{ type: operationType, params: params || {}, label: null }];
  const depsKey = JSON.stringify(ops);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!ops[0]?.type) { setResults(null); return; }

    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const promises = ops.map(op => estimateCredits(op.type, op.params || {}));
        const data = await Promise.all(promises);
        setResults(data);
      } catch {
        setResults(null);
      } finally {
        setLoading(false);
      }
    }, 700);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [depsKey]);

  if (!results && !loading) return null;

  const totalNeeded = results ? results.reduce((sum, r) => sum + (r.credits_needed || 0), 0) : 0;
  const sufficient = isAdmin || (credits >= totalNeeded);

  return (
    <div className={`mt-2 rounded-xl border px-4 py-3 text-xs ${
      sufficient
        ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
        : 'bg-red-50 border-red-200 text-red-800'
    }`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Coins className="w-3.5 h-3.5" />
          <span className="font-bold text-sm">
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader className="w-3 h-3 animate-spin" />
                Calcolo crediti...
              </span>
            ) : (
              <>Crediti necessari: {totalNeeded}</>
            )}
          </span>
        </div>
        {!loading && (
          <span className="opacity-75">
            {isAdmin ? (
              'Crediti illimitati'
            ) : (
              <>Saldo: {credits} {sufficient ? '✓' : '— insufficienti'}</>
            )}
          </span>
        )}
      </div>
      {!loading && results && ops.length > 1 && (
        <div className="flex gap-4 opacity-75 mt-1">
          {results.map((r, i) => {
            const label = ops[i].label || ops[i].type;
            return r.credits_needed > 0 ? (
              <span key={i}>{label}: {r.credits_needed}</span>
            ) : null;
          })}
        </div>
      )}
      {!loading && results && ops.length === 1 && (results[0]?.breakdown?.allegati_crediti > 0) && (
        <div className="flex gap-4 opacity-75 mt-1">
          <span>Generazione testo: {totalNeeded - results[0].breakdown.allegati_crediti}</span>
          <span>Scansione allegati: {results[0].breakdown.allegati_crediti}</span>
        </div>
      )}
    </div>
  );
};

export default CreditEstimatePreview;
