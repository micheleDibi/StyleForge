import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Info, ChevronDown, BookOpen, FileText, ListTree, Sparkles } from 'lucide-react';
import ApiCostEstimate from '../ApiCostEstimate';
import CreditEstimatePreview from '../CreditEstimatePreview';
import CustomOutlineEditor from './CustomOutlineEditor';

const ThesisParametersForm = ({ data, onChange, lookupData, sessions, isAdmin, thesisId, attachmentsCount, attachmentsTotalSize }) => {
  const { t } = useTranslation();
  const handleChange = (field, value) => {
    onChange({ ...data, [field]: value });
  };

  const handleKeyTopicAdd = (topic) => {
    if (topic.trim() && !(data.key_topics || []).includes(topic.trim())) {
      handleChange('key_topics', [...(data.key_topics || []), topic.trim()]);
    }
  };

  const handleKeyTopicRemove = (topic) => {
    handleChange('key_topics', (data.key_topics || []).filter(x => x !== topic));
  };

  // Toggle "Definisci tu indice": passa da modalita' numerica (AI genera) a custom outline.
  const useCustomOutline = !!data.use_custom_outline;

  const setUseCustomOutline = (on) => {
    if (on) {
      // Attiva: se non c'e' ancora un outline, ne inizializzo uno con 1 cap + 1 sez vuoti.
      const init = data.custom_outline || {
        chapters: [{ title: '', brief_description: '', sections: [{ title: '', key_points: [] }] }],
      };
      const numChapters = init.chapters.length;
      const totalSec = init.chapters.reduce((acc, c) => acc + (c.sections?.length || 0), 0);
      const avgSec = Math.max(1, Math.round(totalSec / Math.max(1, numChapters)));
      onChange({
        ...data,
        use_custom_outline: true,
        custom_outline: init,
        num_chapters: numChapters,
        sections_per_chapter: avgSec,
      });
    } else {
      // Disattiva: torno alla modalita' numerica. Mantengo il custom_outline salvato
      // come backup nel caso l'utente riattivi (UX-friendly).
      onChange({
        ...data,
        use_custom_outline: false,
      });
    }
  };

  const handleCustomOutlineChange = (newOutline) => {
    const numChapters = newOutline.chapters.length;
    const totalSec = newOutline.chapters.reduce((acc, c) => acc + (c.sections?.length || 0), 0);
    const avgSec = Math.max(1, Math.round(totalSec / Math.max(1, numChapters)));
    onChange({
      ...data,
      custom_outline: newOutline,
      num_chapters: numChapters,
      sections_per_chapter: avgSec,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">{t('Definizione Parametri di Generazione')}</h2>
        <p className="text-slate-600">{t('Configura i parametri per la generazione della tua tesi o relazione.')}</p>
      </div>

      <div className="card space-y-6">
        {/* Titolo */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {t('Titolo della Tesi')} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={data.title}
            onChange={(e) => handleChange('title', e.target.value)}
            className="input w-full"
            placeholder="es. L'Intelligenza Artificiale nel Settore Sanitario"
            required
          />
        </div>

        {/* Sessione/Addestramento (opzionale) */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {t('Sessione Addestrata (opzionale)')}
          </label>
          <select
            value={data.session_id || ''}
            onChange={(e) => handleChange('session_id', e.target.value || null)}
            className="input w-full"
          >
            <option value="">{t('Nessuna sessione - usa stile generico')}</option>
            {sessions?.filter(s => s.is_trained).map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.name || session.session_id}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-500 mt-1">
            {t("Se selezioni una sessione addestrata, il contenuto userà lo stile dell'autore appreso.")}
          </p>
        </div>

        {/* Descrizione */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {t('Descrizione (opzionale)')}
          </label>
          <textarea
            value={data.description || ''}
            onChange={(e) => handleChange('description', e.target.value)}
            className="input textarea w-full min-h-40 resize-y"
            placeholder={t('Descrivi brevemente di cosa tratterà la tesi...')}
          />
        </div>

        {/* Argomenti Chiave */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {t('Argomenti Chiave (opzionale)')}
          </label>
          <div className="flex flex-wrap gap-2 mb-2">
            {(data.key_topics || []).map((topic, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm"
              >
                {topic}
                <button
                  onClick={() => handleKeyTopicRemove(topic)}
                  className="hover:text-orange-900"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            placeholder={t('Aggiungi argomento e premi Invio')}
            className="input w-full"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleKeyTopicAdd(e.target.value);
                e.target.value = '';
              }
            }}
          />
        </div>

        <div className="border-t border-slate-200 pt-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">{t('Parametri di Generazione')}</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Stile di Scrittura */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                {t('Stile di Scrittura')} <span className="text-red-500">*</span>
              </label>
              <select
                value={data.writing_style_id || ''}
                onChange={(e) => handleChange('writing_style_id', parseInt(e.target.value) || null)}
                className="input w-full"
                required
              >
                <option value="">{t('Seleziona uno stile')}</option>
                {lookupData?.writing_styles?.map((style) => (
                  <option key={style.id} value={style.id}>
                    {style.name}
                  </option>
                ))}
              </select>
              {data.writing_style_id && (
                <p className="text-xs text-slate-500 mt-1">
                  {lookupData?.writing_styles?.find(s => s.id === data.writing_style_id)?.description}
                </p>
              )}
            </div>

            {/* Livello Profondità */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                {t('Livello di Profondità')} <span className="text-red-500">*</span>
              </label>
              <select
                value={data.content_depth_id || ''}
                onChange={(e) => handleChange('content_depth_id', parseInt(e.target.value) || null)}
                className="input w-full"
                required
              >
                <option value="">{t('Seleziona livello')}</option>
                {lookupData?.content_depths?.map((depth) => (
                  <option key={depth.id} value={depth.id}>
                    {depth.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">{t('Struttura del Documento')}</h3>

          {/* Toggle modalita': AI auto-genera VS utente fornisce indice custom */}
          <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setUseCustomOutline(false)}
              className={`text-left p-4 rounded-2xl border-2 transition-all ${
                !useCustomOutline
                  ? 'border-orange-500 bg-orange-50 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Sparkles className={`w-4 h-4 ${!useCustomOutline ? 'text-orange-600' : 'text-slate-400'}`} />
                <span className="font-semibold text-slate-900">{t("L'AI genera l'indice")}</span>
              </div>
              <p className="text-xs text-slate-600">
                {t("Indica il numero di capitoli e paragrafi; l'AI propone titoli che potrai modificare.")}
              </p>
            </button>
            <button
              type="button"
              onClick={() => setUseCustomOutline(true)}
              className={`text-left p-4 rounded-2xl border-2 transition-all ${
                useCustomOutline
                  ? 'border-orange-500 bg-orange-50 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <ListTree className={`w-4 h-4 ${useCustomOutline ? 'text-orange-600' : 'text-slate-400'}`} />
                <span className="font-semibold text-slate-900">{t("Definisci tu l'indice")}</span>
              </div>
              <p className="text-xs text-slate-600">
                {t("Inserisci capitoli e paragrafi a mano. L'AI rispetterà esattamente la struttura fornita.")}
              </p>
            </button>
          </div>

          {!useCustomOutline && (
            <>
              {/* Parole totali - auto distribuzione */}
              <div className="mb-6 p-5 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200 rounded-2xl">
                <div>
                  <label className="block text-sm font-semibold text-slate-800 mb-1">
                    {t('Hai un obiettivo di parole?')}
                  </label>
                    <p className="text-xs text-slate-500 mb-3">
                      {t('Inserisci il totale desiderato e distribuiremo automaticamente le parole tra le sezioni.')}
                    </p>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        placeholder="es. 30000"
                        className="w-40 px-3 py-2 rounded-lg border border-orange-200 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400"
                        min="1000"
                        step="1000"
                        onChange={(e) => {
                          const total = parseInt(e.target.value);
                          if (!total || total < 1000) return;
                          const chapters = data.num_chapters || 5;
                          const sections = data.sections_per_chapter || 3;
                          const wps = Math.round(total / (chapters * sections) / 100) * 100;
                          handleChange('words_per_section', Math.max(500, Math.min(20000, wps)));
                        }}
                      />
                      <span className="text-sm text-slate-500">{t('parole totali')}</span>
                    </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Numero Capitoli */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    {t('Numero di Capitoli')}
                  </label>
                  <input
                    type="number"
                    value={data.num_chapters}
                    onChange={(e) => handleChange('num_chapters', parseInt(e.target.value) || 5)}
                    className="input w-full"
                    min="1"
                    max="100"
                  />
                  <p className="text-xs text-slate-500 mt-1">{t('Default: 5')}</p>
                </div>

                {/* Sezioni per Capitolo */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    {t('Sezioni per Capitolo')}
                  </label>
                  <input
                    type="number"
                    value={data.sections_per_chapter}
                    onChange={(e) => handleChange('sections_per_chapter', parseInt(e.target.value) || 3)}
                    className="input w-full"
                    min="1"
                    max="30"
                  />
                  <p className="text-xs text-slate-500 mt-1">{t('Default: 3')}</p>
                </div>

                {/* Parole per Sezione */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    {t('Parole per Sezione')}
                  </label>
                  <input
                    type="number"
                    value={data.words_per_section}
                    onChange={(e) => handleChange('words_per_section', parseInt(e.target.value) || 1000)}
                    className="input w-full"
                    min="500"
                    max="20000"
                    step="500"
                  />
                  <p className="text-xs text-slate-500 mt-1">{t('Default: 1000')}</p>
                </div>
              </div>
            </>
          )}

          {useCustomOutline && (
            <div className="space-y-4">
              <CustomOutlineEditor
                value={data.custom_outline}
                onChange={handleCustomOutlineChange}
              />

              {/* Parole per Sezione resta configurabile anche in modalita' custom,
                  perche' controlla la lunghezza target del contenuto generato. */}
              <div className="p-4 rounded-2xl border border-slate-200 bg-white">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {t('Parole target per paragrafo')}
                </label>
                <input
                  type="number"
                  value={data.words_per_section}
                  onChange={(e) => handleChange('words_per_section', parseInt(e.target.value) || 1000)}
                  className="input w-full max-w-xs"
                  min="500"
                  max="20000"
                  step="500"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {t('Lunghezza obiettivo del contenuto di ogni paragrafo (vale per tutti). Default: 1000.')}
                </p>
              </div>
            </div>
          )}

          {/* Stima totale */}
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-medium">{t('Stima del documento:')}</p>
                <p>
                  {t('{{chapters}} capitoli × {{sections}} sezioni × {{words}} parole', {
                    chapters: data.num_chapters,
                    sections: data.sections_per_chapter,
                    words: (data.words_per_section || 0).toLocaleString(),
                  })}
                  {' = '}
                  <strong>{(data.num_chapters * data.sections_per_chapter * data.words_per_section).toLocaleString()}</strong>
                  {' '}{t('parole totali')}
                </p>
              </div>
            </div>
          </div>

          {/* Crediti stimati */}
          <CreditEstimatePreview
            operations={[
              { type: 'thesis_chapters', params: { attachment_chars: Math.round((attachmentsTotalSize || 0) * 0.5) }, label: t('Capitoli + allegati') },
              { type: 'thesis_sections', params: {}, label: t('Sezioni') },
              { type: 'thesis_content', params: { num_chapters: data.num_chapters, sections_per_chapter: data.sections_per_chapter, words_per_section: data.words_per_section }, label: t('Contenuto') },
            ]}
          />

          {/* Costo API - solo admin */}
          {isAdmin && (
            <ApiCostEstimate
              mode="thesis"
              numChapters={data.num_chapters}
              sectionsPerChapter={data.sections_per_chapter}
              wordsPerSection={data.words_per_section}
              aiProvider={data.ai_provider}
              thesisId={thesisId}
              attachmentsCount={attachmentsCount || 0}
              attachmentsTotalSize={attachmentsTotalSize || 0}
            />
          )}
        </div>

        {/* Stile Citazioni */}
        <div className="border-t border-slate-200 pt-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">{t('Stile Citazioni')}</h3>
          <div className="flex items-center gap-3 p-4 rounded-xl border-2 border-orange-500 bg-orange-50 text-orange-700">
            <BookOpen className="w-5 h-5 flex-shrink-0" />
            <div>
              <p className="font-semibold">{t('Note a pie di pagina')}</p>
              <p className="text-xs opacity-75">{t('Stile accademico italiano con Ibidem, Ivi, Op.cit.')}</p>
            </div>
          </div>
        </div>

        {/* Knowledge Base (LLM Wiki) — restrict_to_sources */}
        <div className="border-t border-slate-200 pt-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">{t('Base di conoscenza')}</h3>
          <label className="flex items-start gap-3 p-4 rounded-xl border-2 border-slate-200 bg-white hover:border-orange-300 cursor-pointer transition-colors">
            <input
              type="checkbox"
              checked={data.restrict_to_sources !== false}
              onChange={(e) => handleChange('restrict_to_sources', e.target.checked)}
              className="mt-0.5 w-4 h-4 text-orange-600 border-slate-300 rounded focus:ring-orange-500"
            />
            <div className="flex-1">
              <p className="font-semibold text-slate-900">
                {t('Limita la generazione alle sole fonti che caricherò')}
                <span className="ml-2 text-[11px] font-medium text-orange-700 bg-orange-100 rounded px-1.5 py-0.5">{t('consigliato')}</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">
                {t("Se attivo, l'AI userà esclusivamente i paper selezionati e i documenti caricati (indicizzati nel wiki). Riduce le allucinazioni e le citazioni inventate. Disattiva se vuoi che il modello integri liberamente con la sua conoscenza generale.")}
              </p>
            </div>
          </label>
        </div>

      </div>
    </div>
  );
};

export default ThesisParametersForm;
