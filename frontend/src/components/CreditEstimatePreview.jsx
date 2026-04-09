import { useState, useEffect, useRef } from 'react';
import { Coins, Loader } from 'lucide-react';
import { estimateCredits } from '../services/api';
import { useAuth } from '../context/AuthContext';

const CreditEstimatePreview = ({ operationType, params }) => {
  const { isAdmin, credits } = useAuth();
  const [estimate, setEstimate] = useState(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  const depsKey = JSON.stringify({ operationType, params });

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!operationType) { setEstimate(null); return; }

    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const data = await estimateCredits(operationType, params || {});
        setEstimate(data);
      } catch {
        setEstimate(null);
      } finally {
        setLoading(false);
      }
    }, 700);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [depsKey]);

  if (!estimate && !loading) return null;

  const needed = estimate?.credits_needed || 0;
  const sufficient = isAdmin || (credits >= needed);
  const b = estimate?.breakdown || {};

  // Calcola costo generazione (tutto tranne allegati)
  const attachCredits = b.allegati_crediti || 0;
  const genCredits = needed - attachCredits;

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
              <>Crediti necessari: {needed}</>
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
      {!loading && needed > 0 && (genCredits !== needed || attachCredits > 0) && (
        <div className="flex gap-4 opacity-75 mt-1">
          <span>Generazione testo: {genCredits}</span>
          {attachCredits > 0 && <span>Scansione allegati: {attachCredits}</span>}
        </div>
      )}
    </div>
  );
};

export default CreditEstimatePreview;
