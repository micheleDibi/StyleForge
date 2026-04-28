import { useState, useRef } from 'react';
import { Upload, FileText, Link2, Trash2, Info, Loader, CheckCircle, BookMarked } from 'lucide-react';
import { uploadThesisAttachments, deleteThesisAttachment, addThesisUrlAttachments } from '../../services/api';

const PAPER_MIME_TYPE = 'application/x-research-paper';

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const ThesisAttachmentsForm = ({ data, onChange, thesisId }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const [urlText, setUrlText] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlError, setUrlError] = useState(null);

  const handleAddUrls = async () => {
    const lines = urlText.split('\n').map(l => l.trim()).filter(Boolean);
    const validUrls = lines.filter(l => l.startsWith('http://') || l.startsWith('https://'));

    if (validUrls.length === 0) {
      setUrlError('Inserisci almeno un URL valido (deve iniziare con http:// o https://)');
      return;
    }

    setUrlLoading(true);
    setUrlError(null);

    try {
      const result = await addThesisUrlAttachments(thesisId, validUrls);
      onChange({
        ...data,
        attachments: [...data.attachments, ...result.attachments]
      });
      setUrlText('');
    } catch (err) {
      console.error('Errore aggiunta URL:', err);
      setUrlError(err.response?.data?.detail || 'Errore durante il recupero dei contenuti dagli URL');
    } finally {
      setUrlLoading(false);
    }
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    // Validazione
    const validFiles = files.filter(file => {
      const ext = file.name.split('.').pop().toLowerCase();
      const validExtensions = ['pdf', 'docx', 'txt'];
      return validExtensions.includes(ext) && file.size <= 50 * 1024 * 1024;
    });

    if (validFiles.length === 0) {
      setError('Nessun file valido selezionato. Formati supportati: PDF, DOCX, TXT (max 50MB)');
      return;
    }

    if (validFiles.length < files.length) {
      setError(`${files.length - validFiles.length} file ignorati (formato non valido o troppo grandi)`);
    }

    setUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      const result = await uploadThesisAttachments(
        thesisId,
        validFiles,
        (progress) => setUploadProgress(progress)
      );

      onChange({
        ...data,
        attachments: [...data.attachments, ...result.attachments]
      });
    } catch (err) {
      console.error('Errore upload:', err);
      setError(err.response?.data?.detail || 'Errore durante il caricamento dei file');
    } finally {
      setUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveAttachment = async (attachmentId) => {
    try {
      await deleteThesisAttachment(thesisId, attachmentId);
      onChange({
        ...data,
        attachments: data.attachments.filter(a => a.id !== attachmentId)
      });
    } catch (err) {
      console.error('Errore rimozione:', err);
      setError('Errore durante la rimozione del file');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const dataTransfer = new DataTransfer();
      files.forEach(f => dataTransfer.items.add(f));
      if (fileInputRef.current) {
        fileInputRef.current.files = dataTransfer.files;
        handleFileSelect({ target: fileInputRef.current });
      }
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Allegati e Contenuti di Riferimento</h2>
        <p className="text-slate-600">
          Carica documenti che vuoi utilizzare come riferimento per la generazione.
          L'AI analizzerà il contenuto per creare una tesi più accurata e pertinente.
        </p>
      </div>

      <div className="card space-y-6">
        {/* Drop Zone */}
        <div
          className={`
            border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer
            ${uploading
              ? 'border-orange-400 bg-orange-50'
              : 'border-slate-300 hover:border-orange-400 hover:bg-orange-50/50'}
          `}
          onClick={() => !uploading && fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <input
            type="file"
            ref={fileInputRef}
            multiple
            accept=".pdf,.docx,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />

          {uploading ? (
            <div>
              <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
              <p className="text-slate-600 mb-2">Caricamento in corso... {uploadProgress.toFixed(0)}%</p>
              <div className="w-full max-w-xs mx-auto bg-slate-200 rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-orange-500 to-red-500 h-2 rounded-full transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          ) : (
            <>
              <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <p className="text-slate-600 mb-2">
                Trascina qui i file o clicca per selezionarli
              </p>
              <p className="text-sm text-slate-500">
                Formati supportati: PDF, DOCX, TXT (max 50MB per file)
              </p>
            </>
          )}
        </div>

        {/* URL Input Section */}
        <div className="border border-slate-200 rounded-xl p-6 space-y-4">
          <div>
            <h3 className="font-medium text-slate-900 flex items-center gap-2 mb-1">
              <Link2 className="w-4 h-4 text-orange-500" />
              Aggiungi Link come Fonti di Riferimento
            </h3>
            <p className="text-sm text-slate-500">
              Inserisci uno o più URL (uno per riga) da utilizzare come fonti di riferimento.
            </p>
          </div>
          <textarea
            value={urlText}
            onChange={(e) => setUrlText(e.target.value)}
            placeholder={"https://esempio.com/articolo-1\nhttps://esempio.com/articolo-2"}
            rows={4}
            className="input w-full resize-y"
            disabled={urlLoading}
          />
          {urlError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {urlError}
            </div>
          )}
          <button
            onClick={handleAddUrls}
            disabled={urlLoading || !urlText.trim()}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all text-sm
              ${urlLoading || !urlText.trim()
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-orange-100 text-orange-700 hover:bg-orange-200 active:scale-95'
              }
            `}
          >
            {urlLoading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Recupero contenuti...
              </>
            ) : (
              <>
                <Link2 className="w-4 h-4" />
                Aggiungi Link
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Attachments List */}
        {data.attachments.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-medium text-slate-700">File caricati ({data.attachments.length})</h3>
            {data.attachments.map((att) => (
              <div
                key={att.id}
                className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    att.mime_type === PAPER_MIME_TYPE
                      ? 'bg-orange-100'
                      : att.mime_type === 'text/html'
                        ? 'bg-blue-100'
                        : 'bg-orange-100'
                  }`}>
                    {att.mime_type === PAPER_MIME_TYPE ? (
                      <BookMarked className="w-5 h-5 text-orange-600" />
                    ) : att.mime_type === 'text/html' ? (
                      <Link2 className="w-5 h-5 text-blue-600" />
                    ) : (
                      <FileText className="w-5 h-5 text-orange-600" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">{att.original_filename}</p>
                    <p className="text-sm text-slate-500 flex items-center gap-2">
                      {att.mime_type === PAPER_MIME_TYPE ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 border border-orange-200">
                          Paper
                        </span>
                      ) : null}
                      {formatFileSize(att.file_size)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <button
                    onClick={() => handleRemoveAttachment(att.id)}
                    className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                    title="Rimuovi allegato"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">Come vengono utilizzati gli allegati?</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Il testo viene estratto e analizzato dall'AI</li>
                <li>Aiuta a creare contenuti più pertinenti e accurati</li>
                <li>Puoi includere: paper di riferimento, appunti, bozze precedenti</li>
                <li>I file originali non vengono inclusi nel documento finale</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Skip Option */}
        {data.attachments.length === 0 && (
          <p className="text-center text-slate-500 text-sm">
            Gli allegati sono opzionali. Puoi procedere senza caricare file.
          </p>
        )}
      </div>
    </div>
  );
};

export default ThesisAttachmentsForm;
