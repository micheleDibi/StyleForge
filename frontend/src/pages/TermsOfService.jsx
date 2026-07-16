import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const TermsOfService = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen p-6 bg-white">
      <div className="max-w-3xl mx-auto">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-600 hover:text-orange-600 mb-6 text-sm">
          <ArrowLeft className="w-4 h-4" /> {t('Indietro')}
        </button>

        <h1 className="text-3xl font-bold text-slate-900 mb-2">{t('Termini di Servizio')}</h1>
        <p className="text-sm text-slate-500 mb-8">{t('Ultimo aggiornamento: Giugno 2026')}</p>

        <div className="prose prose-slate max-w-none space-y-6 text-sm leading-relaxed text-slate-700">
          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('1. Accettazione dei Termini')}</h2>
            <p>{t("Utilizzando la piattaforma StyleForge, l'utente accetta integralmente i presenti Termini di Servizio. Se non si accettano i termini, non e consentito utilizzare il servizio.")}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('2. Descrizione del Servizio')}</h2>
            <p>{t('StyleForge e una piattaforma AI che permette di:')}</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>{t('Addestrare modelli AI su documenti per apprendere uno stile di scrittura')}</li>
              <li>{t('Generare contenuti originali basati sullo stile appreso')}</li>
              <li>{t('Umanizzare testi generati da AI e ridurne il rilevamento')}</li>
              <li>{t('Generare tesi e documenti accademici completi')}</li>
              <li>{t('Cercare paper accademici e organizzarli in una knowledge base')}</li>
              <li>{t('Verificare i testi con il rilevamento AI/plagio')}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('3. Account e Registrazione')}</h2>
            <p>{t("L'utente e responsabile della sicurezza del proprio account e della riservatezza delle proprie credenziali. E vietato condividere le credenziali con terzi o creare account multipli.")}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('4. Sistema Crediti')}</h2>
            <p>{t("Il servizio funziona con un sistema a crediti. Ogni operazione ha un costo in crediti visibile prima dell'esecuzione. Gli step di generazione falliti o annullati vengono riaccreditati automaticamente; al di fuori di questi casi i crediti consumati non sono rimborsabili. L'acquisto di crediti è gestito dall'amministratore, che si riserva il diritto di modificare i costi delle operazioni.")}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('5. Uso Consentito')}</h2>
            <p>{t("L'utente si impegna a:")}</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>{t('Utilizzare il servizio solo per scopi leciti')}</li>
              <li>{t('Non caricare contenuti illegali, diffamatori o che violano diritti di terzi')}</li>
              <li>{t('Non tentare di aggirare i sistemi di sicurezza o i limiti del servizio')}</li>
              <li>{t('Non utilizzare il servizio per generare contenuti fraudolenti o ingannevoli')}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('6. Proprieta Intellettuale')}</h2>
            <p>{t("I contenuti generati dall'AI tramite il servizio sono di proprieta dell'utente che li ha generati. L'utente e responsabile dell'uso che ne fa. StyleForge non rivendica alcun diritto sui contenuti generati dagli utenti.")}</p>
            <p>{t("L'utente garantisce di avere i diritti sui documenti caricati per l'addestramento.")}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('7. Limitazione di Responsabilita')}</h2>
            <p>{t('StyleForge fornisce il servizio "cosi com\'e". Non garantiamo che i contenuti generati siano privi di errori, originali al 100% o adatti a scopi specifici. L\'utente e l\'unico responsabile dell\'uso dei contenuti generati.')}</p>
            <p>{t('Non siamo responsabili per danni diretti o indiretti derivanti dall\'uso del servizio, inclusi ma non limitati a: perdita di dati, interruzioni del servizio, risultati non soddisfacenti.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('8. Disponibilita del Servizio')}</h2>
            <p>{t('Ci impegniamo a garantire la massima disponibilita del servizio, ma non garantiamo un uptime del 100%. Manutenzioni programmate e aggiornamenti possono causare interruzioni temporanee.')}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('9. Modifiche ai Termini')}</h2>
            <p>{t("Ci riserviamo il diritto di modificare i presenti Termini di Servizio. Le modifiche saranno comunicate tramite la piattaforma. L'uso continuato del servizio dopo la notifica costituisce accettazione delle modifiche.")}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">{t('10. Legge Applicabile')}</h2>
            <p>{t('I presenti Termini sono regolati dalla legge italiana. Per qualsiasi controversia e competente il Foro del luogo di residenza del titolare del servizio.')}</p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
