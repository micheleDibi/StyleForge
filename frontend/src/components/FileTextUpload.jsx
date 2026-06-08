import { useRef, useState } from 'react';
import { Upload, Loader, AlertTriangle } from 'lucide-react';
import { extractTextFromFile } from '../services/api';

const ACCEPT = '.pdf,.docx,.txt';

/**
 * Caricatore di file riusabile per estrarre testo da PDF/DOCX/TXT.
 * Il file NON viene salvato sul server: il backend (/extract-text) lo legge,
 * ne estrae il testo e lo elimina. Al successo invoca onExtracted(text, filename).
 *
 * Props:
 *  - onExtracted(text, filename): callback con il testo estratto
 *  - disabled: disabilita il caricamento (es. durante elaborazione/scansione)
 *  - className: classi extra per il contenitore
 */
const FileTextUpload = ({ onExtracted, disabled = false, className = '' }) => {
  const inputRef = useRef(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const isBusy = disabled || extracting;

  const handleFile = async (file) => {
    if (!file) return;
    setError(null);
    setExtracting(true);
    try {
      const data = await extractTextFromFile(file);
      if (data?.text) {
        onExtracted(data.text, data.filename);
      } else {
        setError('Nessun testo estratto dal file.');
      }
    } catch (err) {
      console.error('Errore estrazione file:', err);
      setError(err.response?.data?.detail || "Errore durante l'estrazione del testo dal file");
    } finally {
      setExtracting(false);
    }
  };

  const handleChange = (e) => {
    const file = e.target.files?.[0];
    // Reset immediato: così ricaricare lo stesso file rifa partire onChange
    e.target.value = '';
    handleFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (isBusy) return;
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  return (
    <div className={className}>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        onChange={handleChange}
        className="hidden"
        disabled={isBusy}
      />
      <div
        onClick={() => !isBusy && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!isBusy) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-dashed text-sm font-medium transition-all ${
          isBusy
            ? 'opacity-60 cursor-not-allowed border-slate-200 text-slate-400'
            : dragOver
              ? 'border-indigo-400 bg-indigo-50 text-indigo-700 cursor-pointer'
              : 'border-slate-300 text-slate-600 hover:border-indigo-300 hover:bg-slate-50 cursor-pointer'
        }`}
      >
        {extracting ? (
          <>
            <Loader className="w-4 h-4 animate-spin" />
            Estrazione testo in corso...
          </>
        ) : (
          <>
            <Upload className="w-4 h-4" />
            Carica file (PDF, DOCX, TXT) o trascinalo qui
          </>
        )}
      </div>
      {error && (
        <div className="mt-2 bg-red-50 border border-red-200 rounded-lg p-2 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <span className="text-red-700 text-xs">{error}</span>
        </div>
      )}
    </div>
  );
};

export default FileTextUpload;
