import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const PrivacyPolicy = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen p-6 bg-white">
      <div className="max-w-3xl mx-auto">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-600 hover:text-orange-600 mb-6 text-sm">
          <ArrowLeft className="w-4 h-4" /> Indietro
        </button>

        <h1 className="text-3xl font-bold text-slate-900 mb-2">Informativa sulla Privacy</h1>
        <p className="text-sm text-slate-500 mb-8">Ultimo aggiornamento: Aprile 2026</p>

        <div className="prose prose-slate max-w-none space-y-6 text-sm leading-relaxed text-slate-700">
          <section>
            <h2 className="text-lg font-semibold text-slate-900">1. Titolare del Trattamento</h2>
            <p>Il titolare del trattamento dei dati personali e il gestore della piattaforma StyleForge. Per qualsiasi richiesta relativa alla privacy, contattare l'indirizzo email indicato nella sezione contatti.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">2. Dati Raccolti</h2>
            <p>Raccogliamo i seguenti dati:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Dati di registrazione:</strong> email, username, nome completo (opzionale), password (hashata)</li>
              <li><strong>Dati di utilizzo:</strong> sessioni di addestramento, contenuti generati, tesi create, crediti consumati</li>
              <li><strong>Documenti caricati:</strong> file PDF, DOCX, TXT e link web forniti come allegati per la generazione tesi</li>
              <li><strong>Dati tecnici:</strong> indirizzo IP, tipo di browser, timestamp delle richieste</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">3. Finalita del Trattamento</h2>
            <p>I dati vengono trattati per:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Fornire i servizi della piattaforma (addestramento AI, generazione contenuti, tesi)</li>
              <li>Gestire l'autenticazione e la sicurezza dell'account</li>
              <li>Gestire il sistema crediti e la fatturazione</li>
              <li>Migliorare la qualita del servizio</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">4. Condivisione con Terze Parti</h2>
            <p>I contenuti dei documenti caricati e i testi inseriti vengono inviati ai servizi AI di Anthropic (Claude) e OpenAI per l'elaborazione. Questi servizi operano come responsabili del trattamento e sono soggetti alle rispettive politiche sulla privacy.</p>
            <p>Non vendiamo ne condividiamo i dati personali con altre terze parti per scopi di marketing.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">5. Conservazione dei Dati</h2>
            <p>I dati vengono conservati per la durata dell'account attivo. Le sessioni non addestrate vengono eliminate automaticamente dopo 24 ore. Le sessioni addestrate restano disponibili indefinitamente.</p>
            <p>Alla cancellazione dell'account, tutti i dati personali e i contenuti generati vengono eliminati.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">6. Diritti dell'Utente (GDPR)</h2>
            <p>In conformita al Regolamento UE 2016/679 (GDPR), l'utente ha diritto a:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Accesso:</strong> richiedere una copia dei propri dati personali</li>
              <li><strong>Rettifica:</strong> correggere dati inesatti o incompleti</li>
              <li><strong>Cancellazione:</strong> richiedere la cancellazione dei propri dati ("diritto all'oblio")</li>
              <li><strong>Portabilita:</strong> ricevere i propri dati in formato strutturato e leggibile</li>
              <li><strong>Opposizione:</strong> opporsi al trattamento dei propri dati</li>
            </ul>
            <p>Per esercitare questi diritti, contattare il titolare del trattamento tramite i canali indicati.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">7. Sicurezza</h2>
            <p>Adottiamo misure tecniche e organizzative per proteggere i dati: autenticazione JWT, hashing password con bcrypt, comunicazioni HTTPS, controllo accessi basato su ruoli.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">8. Cookie</h2>
            <p>La piattaforma utilizza localStorage per la gestione dei token di autenticazione. Non utilizziamo cookie di profilazione o di terze parti per scopi pubblicitari.</p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
