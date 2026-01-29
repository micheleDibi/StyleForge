import { useState, useEffect } from 'react';
import { Info, ChevronDown, Cpu, Sparkles } from 'lucide-react';

const ThesisParametersForm = ({ data, onChange, lookupData, sessions }) => {
  const handleChange = (field, value) => {
    onChange({ ...data, [field]: value });
  };

  const handleKeyTopicAdd = (topic) => {
    if (topic.trim() && !(data.key_topics || []).includes(topic.trim())) {
      handleChange('key_topics', [...(data.key_topics || []), topic.trim()]);
    }
  };

  const handleKeyTopicRemove = (topic) => {
    handleChange('key_topics', (data.key_topics || []).filter(t => t !== topic));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Definizione Parametri di Generazione</h2>
        <p className="text-slate-600">Configura i parametri per la generazione della tua tesi o relazione.</p>
      </div>

      <div className="card space-y-6">
        {/* Titolo */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Titolo della Tesi <span className="text-red-500">*</span>
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

        {/* Provider AI */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Modello AI <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleChange('ai_provider', 'openai')}
              className={`flex items-center justify-center gap-2 p-4 rounded-xl border-2 transition-all ${
                data.ai_provider === 'openai'
                  ? 'border-green-500 bg-green-50 text-green-700'
                  : 'border-slate-200 hover:border-slate-300 text-slate-600'
              }`}
            >
              <Cpu className="w-5 h-5" />
              <div className="text-left">
                <p className="font-semibold">OpenAI</p>
                <p className="text-xs opacity-75">o1-preview</p>
              </div>
            </button>
            <button
              type="button"
              onClick={() => handleChange('ai_provider', 'claude')}
              className={`flex items-center justify-center gap-2 p-4 rounded-xl border-2 transition-all ${
                data.ai_provider === 'claude'
                  ? 'border-purple-500 bg-purple-50 text-purple-700'
                  : 'border-slate-200 hover:border-slate-300 text-slate-600'
              }`}
            >
              <Sparkles className="w-5 h-5" />
              <div className="text-left">
                <p className="font-semibold">Claude</p>
                <p className="text-xs opacity-75">Sonnet 4</p>
              </div>
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Seleziona il modello AI da usare per la generazione del contenuto.
          </p>
        </div>

        {/* Sessione/Addestramento (opzionale) */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Sessione Addestrata (opzionale)
          </label>
          <select
            value={data.session_id || ''}
            onChange={(e) => handleChange('session_id', e.target.value || null)}
            className="input w-full"
          >
            <option value="">Nessuna sessione - usa stile generico</option>
            {sessions?.filter(s => s.is_trained).map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.name || session.session_id}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-500 mt-1">
            Se selezioni una sessione addestrata, il contenuto userà lo stile dell'autore appreso.
          </p>
        </div>

        {/* Descrizione */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Descrizione (opzionale)
          </label>
          <textarea
            value={data.description || ''}
            onChange={(e) => handleChange('description', e.target.value)}
            className="input w-full h-24 resize-y"
            placeholder="Descrivi brevemente di cosa tratterà la tesi..."
          />
        </div>

        {/* Argomenti Chiave */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Argomenti Chiave (opzionale)
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
            placeholder="Aggiungi argomento e premi Invio"
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
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Parametri di Generazione</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Stile di Scrittura */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Stile di Scrittura <span className="text-red-500">*</span>
              </label>
              <select
                value={data.writing_style_id || ''}
                onChange={(e) => handleChange('writing_style_id', parseInt(e.target.value) || null)}
                className="input w-full"
                required
              >
                <option value="">Seleziona uno stile</option>
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
                Livello di Profondità <span className="text-red-500">*</span>
              </label>
              <select
                value={data.content_depth_id || ''}
                onChange={(e) => handleChange('content_depth_id', parseInt(e.target.value) || null)}
                className="input w-full"
                required
              >
                <option value="">Seleziona livello</option>
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
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Struttura del Documento</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Numero Capitoli */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Numero di Capitoli
              </label>
              <input
                type="number"
                value={data.num_chapters}
                onChange={(e) => handleChange('num_chapters', parseInt(e.target.value) || 5)}
                className="input w-full"
                min="1"
                max="20"
              />
              <p className="text-xs text-slate-500 mt-1">Default: 5</p>
            </div>

            {/* Sezioni per Capitolo */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Sezioni per Capitolo
              </label>
              <input
                type="number"
                value={data.sections_per_chapter}
                onChange={(e) => handleChange('sections_per_chapter', parseInt(e.target.value) || 3)}
                className="input w-full"
                min="1"
                max="10"
              />
              <p className="text-xs text-slate-500 mt-1">Default: 3</p>
            </div>

            {/* Parole per Sezione */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Parole per Sezione
              </label>
              <input
                type="number"
                value={data.words_per_section}
                onChange={(e) => handleChange('words_per_section', parseInt(e.target.value) || 5000)}
                className="input w-full"
                min="500"
                max="20000"
                step="500"
              />
              <p className="text-xs text-slate-500 mt-1">Default: 5000</p>
            </div>
          </div>

          {/* Stima totale */}
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-medium">Stima del documento:</p>
                <p>
                  {data.num_chapters} capitoli × {data.sections_per_chapter} sezioni × {(data.words_per_section || 0).toLocaleString()} parole
                  = <strong>{(data.num_chapters * data.sections_per_chapter * data.words_per_section).toLocaleString()}</strong> parole totali
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThesisParametersForm;
