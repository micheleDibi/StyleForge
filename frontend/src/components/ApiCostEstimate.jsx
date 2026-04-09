import { useState, useEffect, useRef } from 'react';
import { DollarSign, Loader } from 'lucide-react';
import { estimateApiCost } from '../services/api';

const ApiCostEstimate = ({ mode, wordCount, sessionId }) => {
  const [estimate, setEstimate] = useState(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (wordCount < 10) {
      setEstimate(null);
      return;
    }

    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const data = await estimateApiCost(
          mode,
          wordCount,
          mode === 'full' ? sessionId : null
        );
        setEstimate(data);
      } catch {
        setEstimate(null);
      } finally {
        setLoading(false);
      }
    }, 700);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [mode, wordCount, sessionId]);

  if (!estimate && !loading) return null;

  const themeColor = mode === 'correction' ? 'amber' : 'violet';

  const formatTokens = (n) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return n.toString();
  };

  return (
    <div className={`mt-2 rounded-lg border px-3 py-2 text-xs ${
      mode === 'correction'
        ? 'bg-amber-50 border-amber-200 text-amber-800'
        : 'bg-violet-50 border-violet-200 text-violet-800'
    }`}>
      {loading ? (
        <div className="flex items-center gap-2">
          <Loader className="w-3 h-3 animate-spin" />
          <span>Stima costo API...</span>
        </div>
      ) : estimate ? (
        <div className="flex items-center gap-2 flex-wrap">
          <DollarSign className="w-3 h-3 flex-shrink-0" />
          <span className="font-semibold">
            Costo API stimato: ~{estimate.estimated_cost_eur.toFixed(4)} EUR
          </span>
          <span className="text-[10px] opacity-70">
            Input: ~{formatTokens(estimate.breakdown.input_tokens)} tok ({estimate.breakdown.input_cost_eur.toFixed(4)} EUR)
            {' | '}
            Output: ~{formatTokens(estimate.breakdown.output_tokens)} tok ({estimate.breakdown.output_cost_eur.toFixed(4)} EUR)
          </span>
        </div>
      ) : null}
    </div>
  );
};

export default ApiCostEstimate;
