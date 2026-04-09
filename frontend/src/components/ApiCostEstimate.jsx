import { useState, useEffect, useRef } from 'react';
import { DollarSign, Loader } from 'lucide-react';
import { estimateApiCost } from '../services/api';

// Pricing constants (fallback client-side)
const CLAUDE_INPUT_PRICE_EUR = 15.0 * 0.88;  // $/MTok * EUR rate
const CLAUDE_OUTPUT_PRICE_EUR = 75.0 * 0.88;
const TOKENS_PER_WORD = 2.5;
const CORRECTION_PROMPT_WORDS = 560;
const FULL_PROMPT_WORDS = 350;
const FULL_SYSTEM_TOKENS = 200;

const computeLocalEstimate = (mode, wordCount) => {
  let inputTokens, outputTokens;

  if (mode === 'correction') {
    inputTokens = Math.round((CORRECTION_PROMPT_WORDS + wordCount) * TOKENS_PER_WORD);
    outputTokens = Math.round(wordCount * TOKENS_PER_WORD);
  } else {
    // Full mode: senza conversation history, stima conservativa di 50k token
    const historyTokens = 50000;
    inputTokens = FULL_SYSTEM_TOKENS + historyTokens + Math.round((FULL_PROMPT_WORDS + wordCount) * TOKENS_PER_WORD);
    outputTokens = Math.round(wordCount * TOKENS_PER_WORD);
  }

  const inputCostEur = (inputTokens / 1_000_000) * CLAUDE_INPUT_PRICE_EUR;
  const outputCostEur = (outputTokens / 1_000_000) * CLAUDE_OUTPUT_PRICE_EUR;

  return {
    estimated_cost_eur: Math.round((inputCostEur + outputCostEur) * 10000) / 10000,
    breakdown: {
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      input_cost_eur: Math.round(inputCostEur * 10000) / 10000,
      output_cost_eur: Math.round(outputCostEur * 10000) / 10000,
    },
    is_local: true,
  };
};

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

    // Mostra subito stima locale, poi aggiorna con quella server-side
    setEstimate(computeLocalEstimate(mode, wordCount));
    setLoading(true);

    timerRef.current = setTimeout(async () => {
      try {
        const data = await estimateApiCost(
          mode,
          wordCount,
          mode === 'full' ? sessionId : null
        );
        setEstimate({ ...data, is_local: false });
      } catch {
        // Mantieni la stima locale come fallback
      } finally {
        setLoading(false);
      }
    }, 700);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [mode, wordCount, sessionId]);

  if (!estimate) return null;

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
      <div className="flex items-center gap-2 flex-wrap">
        <DollarSign className="w-3 h-3 flex-shrink-0" />
        <span className="font-semibold">
          Costo API stimato: ~{estimate.estimated_cost_eur.toFixed(4)} EUR
        </span>
        {loading && <Loader className="w-3 h-3 animate-spin opacity-50" />}
        <span className="text-[10px] opacity-70">
          Input: ~{formatTokens(estimate.breakdown.input_tokens)} tok ({estimate.breakdown.input_cost_eur.toFixed(4)} EUR)
          {' | '}
          Output: ~{formatTokens(estimate.breakdown.output_tokens)} tok ({estimate.breakdown.output_cost_eur.toFixed(4)} EUR)
          {estimate.is_local && mode === 'full' ? ' (stima approssimativa)' : ''}
        </span>
      </div>
    </div>
  );
};

export default ApiCostEstimate;
