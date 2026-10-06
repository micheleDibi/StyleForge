import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const PrivacyPolicy = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen p-6 bg-white">
      <div className="max-w-3xl mx-auto">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-600 hover:text-orange-600 mb-6 text-sm">
          <ArrowLeft className="w-4 h-4" /> {t('Indietro')}
        </button>

        <h1 className="text-3xl font-bold text-slate-900 mb-2">{t('Informativa sulla Privacy')}</h1>
        <p className="text-sm text-slate-500 mb-8">{t('Ultimo aggiornamento: Giugno 2026')}</p>

        <div className="prose prose-slate max-w-none space-y-6 text-sm leading-relaxed text-slate-700">
          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('1. Titolare del Trattamento')}</h2>
            <p>{t('Il titolare del trattamento dei dati personali e il gestore della piattaforma StyleForge. Per qualsiasi richiesta relativa alla privacy, contattare l\'indirizzo email indicato nella sezione contatti.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('2. Dati Raccolti')}</h2>
            <p>{t('Raccogliamo i seguenti dati:')}</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>{t('Dati di registrazione:')}</strong> {t('email, username, nome completo (opzionale), password (hashata)')}</li>
              <li><strong>{t('Dati di utilizzo:')}</strong> {t('sessioni di addestramento, contenuti generati, tesi create, crediti consumati')}</li>
              <li><strong>{t('Documenti caricati:')}</strong> {t('file PDF, DOCX, TXT e link web forniti come allegati per la generazione tesi')}</li>
              <li><strong>{t('Dati tecnici:')}</strong> {t('indirizzo IP, tipo di browser, timestamp delle richieste')}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('3. Finalita del Trattamento')}</h2>
            <p>{t('I dati vengono trattati per:')}</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>{t('Fornire i servizi della piattaforma (addestramento AI, generazione contenuti, tesi, ricerca accademica, rilevamento AI)')}</li>
              <li>{t('Gestire l\'autenticazione e la sicurezza dell\'account')}</li>
              <li>{t('Gestire il sistema crediti')}</li>
              <li>{t('Migliorare la qualita del servizio')}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('4. Condivisione con Terze Parti')}</h2>
            <p>{t('I contenuti dei documenti caricati e i testi inseriti vengono inviati ai servizi AI di Anthropic (Claude) e, se attivato, OpenAI per l\'elaborazione. La funzione di rilevamento AI/plagio invia il testo da analizzare al servizio Compilatio. Questi servizi operano come responsabili del trattamento e sono soggetti alle rispettive politiche sulla privacy.')}</p>
            <p>{t('Non vendiamo ne condividiamo i dati personali con altre terze parti per scopi di marketing.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('5. Conservazione dei Dati')}</h2>
            <p>{t('I dati vengono conservati per la durata dell\'account attivo. Le sessioni non addestrate vengono eliminate automaticamente dopo 24 ore. Le sessioni addestrate restano disponibili indefinitamente.')}</p>
            <p>{t('Alla cancellazione dell\'account, tutti i dati personali e i contenuti generati vengono eliminati.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('6. Diritti dell\'Utente (GDPR)')}</h2>
            <p>{t('In conformita al Regolamento UE 2016/679 (GDPR), l\'utente ha diritto a:')}</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>{t('Accesso:')}</strong> {t('richiedere una copia dei propri dati personali')}</li>
              <li><strong>{t('Rettifica:')}</strong> {t('correggere dati inesatti o incompleti')}</li>
              <li><strong>{t('Cancellazione:')}</strong> {t('richiedere la cancellazione dei propri dati ("diritto all\'oblio")')}</li>
              <li><strong>{t('Portabilita:')}</strong> {t('ricevere i propri dati in formato strutturato e leggibile')}</li>
              <li><strong>{t('Opposizione:')}</strong> {t('opporsi al trattamento dei propri dati')}</li>
            </ul>
            <p>{t('Per esercitare questi diritti, contattare il titolare del trattamento tramite i canali indicati.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('7. Sicurezza')}</h2>
            <p>{t('Adottiamo misure tecniche e organizzative per proteggere i dati: autenticazione JWT, hashing password con bcrypt, comunicazioni HTTPS, controllo accessi basato su ruoli.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('8. Cookie')}</h2>
            <p>{t('La piattaforma utilizza localStorage per la gestione dei token di autenticazione. Non utilizziamo cookie di profilazione o di terze parti per scopi pubblicitari.')}</p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
