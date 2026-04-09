import { useState, useEffect, useRef } from 'react';
import { DollarSign, Loader } from 'lucide-react';
import { estimateApiCost } from '../services/api';

// Pricing constants (fallback client-side)
const CLAUDE_INPUT_EUR = 15.0 * 0.88;
const CLAUDE_OUTPUT_EUR = 75.0 * 0.88;
const OPENAI_INPUT_EUR = 10.0 * 0.88;
const OPENAI_OUTPUT_EUR = 40.0 * 0.88;
const TPW = 2.5; // tokens per word (italiano)

const calcCost = (inputTok, outputTok, provider) => {
  const inPrice = provider === 'openai' ? OPENAI_INPUT_EUR : CLAUDE_INPUT_EUR;
  const outPrice = provider === 'openai' ? OPENAI_OUTPUT_EUR : CLAUDE_OUTPUT_EUR;
  const inCost = (inputTok / 1_000_000) * inPrice;
  const outCost = (outputTok / 1_000_000) * outPrice;
  return {
    estimated_cost_eur: Math.round((inCost + outCost) * 10000) / 10000,
    breakdown: {
      input_tokens: inputTok,
      output_tokens: outputTok,
      input_cost_eur: Math.round(inCost * 10000) / 10000,
      output_cost_eur: Math.round(outCost * 10000) / 10000,
    },
    is_local: true,
  };
};

const computeLocalEstimate = (props) => {
  const { mode, wordCount = 0, maxPages, numWords, numChapters, sectionsPerChapter, wordsPerSection, aiProvider } = props;

  if (mode === 'correction') {
    return calcCost(Math.round((560 + wordCount) * TPW), Math.round(wordCount * TPW), 'claude');
  }
  if (mode === 'full') {
    const input = 200 + 50000 + Math.round((350 + wordCount) * TPW);
    return calcCost(input, Math.round(wordCount * TPW), 'claude');
  }
  if (mode === 'train') {
    const pages = maxPages || 50;
    return calcCost(Math.round((2000 + 250 * pages) * TPW), 4096, 'claude');
  }
  if (mode === 'generate') {
    const words = numWords || wordCount || 1000;
    const input = 200 + 50000 + Math.round((100 + words) * TPW);
    return calcCost(input, Math.round(words * TPW), 'claude');
  }
  if (mode === 'thesis') {
    const nc = numChapters || 5;
    const spc = sectionsPerChapter || 3;
    const wps = wordsPerSection || 1000;
    const totalSections = nc * spc;
    const provider = aiProvider || 'openai';
    const input = Math.round(500 * TPW) + Math.round(500 * TPW) + totalSections * Math.round(800 * TPW);
    const output = Math.round(200 * TPW) + Math.round(300 * TPW) + totalSections * Math.round(wps * TPW);
    return calcCost(input, output, provider);
  }
  return null;
};

const THEME = {
  correction: 'bg-amber-50 border-amber-200 text-amber-800',
  full: 'bg-violet-50 border-violet-200 text-violet-800',
  train: 'bg-blue-50 border-blue-200 text-blue-800',
  generate: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  thesis: 'bg-orange-50 border-orange-200 text-orange-800',
};

const ApiCostEstimate = (props) => {
  const { mode } = props;
  const [estimate, setEstimate] = useState(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  // Chiave di dipendenza: serializza le props rilevanti
  const depsKey = JSON.stringify(props);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    const local = computeLocalEstimate(props);
    if (!local) { setEstimate(null); return; }

    setEstimate(local);
    setLoading(true);

    timerRef.current = setTimeout(async () => {
      try {
        const body = {
          mode,
          word_count: props.wordCount || 0,
          session_id: props.sessionId || null,
          max_pages: props.maxPages || null,
          num_words: props.numWords || null,
          num_chapters: props.numChapters || null,
          sections_per_chapter: props.sectionsPerChapter || null,
          words_per_section: props.wordsPerSection || null,
          ai_provider: props.aiProvider || null,
        };
        const data = await estimateApiCost(body);
        setEstimate({ ...data, is_local: false });
      } catch {
        // Mantieni stima locale
      } finally {
        setLoading(false);
      }
    }, 700);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [depsKey]);

  if (!estimate) return null;

  const fmt = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toString();
  const needsApprox = estimate.is_local && ['full', 'generate'].includes(mode);

  return (
    <div className={`mt-2 rounded-lg border px-3 py-2 text-xs ${THEME[mode] || THEME.train}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <DollarSign className="w-3 h-3 flex-shrink-0" />
        <span className="font-semibold">
          Costo API stimato: ~{estimate.estimated_cost_eur.toFixed(4)} EUR
        </span>
        {loading && <Loader className="w-3 h-3 animate-spin opacity-50" />}
        <span className="text-[10px] opacity-70">
          Input: ~{fmt(estimate.breakdown.input_tokens)} tok ({estimate.breakdown.input_cost_eur.toFixed(4)} EUR)
          {' | '}
          Output: ~{fmt(estimate.breakdown.output_tokens)} tok ({estimate.breakdown.output_cost_eur.toFixed(4)} EUR)
          {needsApprox ? ' (stima approssimativa)' : ''}
        </span>
      </div>
    </div>
  );
};

export default ApiCostEstimate;
