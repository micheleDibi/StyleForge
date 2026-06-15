import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Coins, CreditCard, Loader, Package, Sparkles, Shield, AlertTriangle, Check, Info, ArrowRight,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { listCreditPackages, initiatePayment } from '../services/api';

const CF_REGEX = /^[A-Z0-9]{16}$/;
const PI_REGEX = /^[0-9]{11}$/;

const formatEur = (cents) => {
  if (typeof cents !== 'number') return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100);
};

const BuyCredits = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, isAdmin, credits } = useAuth();

  const [packages, setPackages] = useState([]);
  const [loadingPackages, setLoadingPackages] = useState(true);
  const [errorPackages, setErrorPackages] = useState(null);

  const [selectedPkgId, setSelectedPkgId] = useState(null);

  // Form pagatore (precompilato dal profilo se disponibile)
  const [codiceFiscale, setCodiceFiscale] = useState((user?.codice_fiscale || '').toUpperCase());
  const [partitaIva, setPartitaIva] = useState(user?.partita_iva || '');
  const [ragioneSociale, setRagioneSociale] = useState(user?.ragione_sociale || '');
  const [payerEmail, setPayerEmail] = useState(user?.email || '');
  const [saveToProfile, setSaveToProfile] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listCreditPackages();
        if (cancelled) return;
        setPackages(res.packages || []);
        // Pre-select del pacchetto medio (sort_order 2) se presente
        const mid = (res.packages || []).find((p) => p.sort_order === 2) || (res.packages || [])[0];
        if (mid) setSelectedPkgId(mid.id);
      } catch (err) {
        if (!cancelled) setErrorPackages(t('Errore caricamento pacchetti.'));
      } finally {
        if (!cancelled) setLoadingPackages(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Admin escluso
  useEffect(() => {
    if (isAdmin) {
      // Reindirizza alla dashboard con messaggio
      const timer = setTimeout(() => navigate('/'), 100);
      return () => clearTimeout(timer);
    }
  }, [isAdmin, navigate]);

  const selectedPkg = useMemo(
    () => packages.find((p) => p.id === selectedPkgId),
    [packages, selectedPkgId]
  );

  const cfNormalized = (codiceFiscale || '').toUpperCase().trim();
  const piTrimmed = (partitaIva || '').trim();
  const cfValid = CF_REGEX.test(cfNormalized) || PI_REGEX.test(cfNormalized);
  const piValid = !piTrimmed || PI_REGEX.test(piTrimmed);

  const canSubmit = !!selectedPkg && cfValid && piValid && !submitting;

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!canSubmit || !selectedPkg) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      const result = await initiatePayment({
        package_id: selectedPkg.id,
        codice_fiscale: cfNormalized,
        partita_iva: piTrimmed || null,
        ragione_sociale: ragioneSociale.trim() || null,
        payer_email: payerEmail.trim() || null,
        save_to_profile: saveToProfile,
      });
      if (result?.checkout_url) {
        window.location.href = result.checkout_url;
        return;
      }
      setSubmitError(t('Risposta non valida dal server.'));
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || t('Errore avvio pagamento');
      setSubmitError(typeof detail === 'string' ? detail : t('Errore avvio pagamento'));
    } finally {
      setSubmitting(false);
    }
  };

  if (isAdmin) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="glass rounded-2xl p-6 flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-emerald-500" />
          <p className="text-slate-700">{t('Gli admin StyleForge hanno crediti illimitati. Reindirizzamento alla dashboard…')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">{t('Acquista Crediti')}</h1>
          <p className="text-slate-600 mt-1">
            {t('Paga con PagoPA (carta di credito, conto corrente, MyBank). I crediti vengono accreditati immediatamente.')}
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-orange-50 rounded-xl border border-orange-200">
          <Coins className="w-4 h-4 text-orange-500" />
          <span className="text-sm font-bold text-orange-700">{credits}</span>
          <span className="text-xs text-orange-500">{t('crediti attuali')}</span>
        </div>
      </div>

      {/* Pacchetti */}
      <div className="space-y-3">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2">
          <Package className="w-5 h-5 text-orange-500" />
          {t('Scegli un pacchetto')}
        </h2>

        {loadingPackages ? (
          <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
            <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento pacchetti…')}
          </div>
        ) : errorPackages ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errorPackages}</div>
        ) : packages.length === 0 ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {t("Nessun pacchetto al momento disponibile. Contatta l'amministratore.")}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {packages.map((pkg, i) => {
              const selected = selectedPkgId === pkg.id;
              const isFeatured = pkg.sort_order === 2 && packages.length >= 3;
              return (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => setSelectedPkgId(pkg.id)}
                  className={`relative text-left p-5 rounded-2xl border-2 transition-all ${
                    selected
                      ? 'border-orange-500 bg-orange-50 shadow-md'
                      : 'border-slate-200 bg-white hover:border-orange-300'
                  }`}
                >
                  {isFeatured && (
                    <span className="absolute -top-2 right-4 px-2 py-0.5 rounded-full bg-orange-500 text-white text-[10px] font-bold uppercase">
                      {t('Più scelto')}
                    </span>
                  )}
                  {selected && (
                    <span className="absolute top-3 left-3 w-6 h-6 rounded-full bg-orange-500 text-white flex items-center justify-center">
                      <Check className="w-4 h-4" />
                    </span>
                  )}
                  <div className="text-sm font-semibold text-slate-500 uppercase tracking-wide">{pkg.name}</div>
                  <div className="mt-2 text-3xl font-bold text-slate-900">
                    {pkg.credits.toLocaleString('it-IT')}
                  </div>
                  <div className="text-xs text-slate-500 mb-3">{t('crediti')}</div>
                  <div className="text-xl font-bold text-orange-600">{formatEur(pkg.price_cents)}</div>
                  {pkg.description && (
                    <p className="mt-2 text-xs text-slate-500">{pkg.description}</p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Form pagatore */}
      {selectedPkg && (
        <form onSubmit={handleSubmit} className="glass rounded-2xl p-6 space-y-5">
          <div className="flex items-center gap-2 mb-1">
            <CreditCard className="w-5 h-5 text-orange-500" />
            <h2 className="font-semibold text-slate-900">{t('Dati pagatore')}</h2>
          </div>
          <p className="text-sm text-slate-500">
            {t('Per emettere la posizione PagoPA serve un identificativo del pagatore (CF persona fisica o P.IVA per soggetti giuridici).')}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t('Codice Fiscale o P.IVA')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                className="input w-full uppercase"
                value={codiceFiscale}
                onChange={(e) => setCodiceFiscale(e.target.value.toUpperCase())}
                placeholder="RSSMRA80A01H501Z"
                maxLength={16}
                required
              />
              {!cfValid && cfNormalized.length > 0 && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {t('Formato non valido (16 alfanumerici, oppure 11 cifre per P.IVA)')}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t('Partita IVA (se soggetto giuridico)')}
              </label>
              <input
                type="text"
                className="input w-full"
                value={partitaIva}
                onChange={(e) => setPartitaIva(e.target.value)}
                placeholder={t('11 cifre')}
                maxLength={11}
              />
              {!piValid && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> {t('P.IVA deve essere 11 cifre')}
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">{t('Ragione sociale (se ente/azienda)')}</label>
              <input
                type="text"
                className="input w-full"
                value={ragioneSociale}
                onChange={(e) => setRagioneSociale(e.target.value)}
                placeholder="Es. Acme S.r.l."
                maxLength={255}
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">{t('Email pagatore')}</label>
              <input
                type="email"
                className="input w-full"
                value={payerEmail}
                onChange={(e) => setPayerEmail(e.target.value)}
                placeholder="email@example.com"
              />
            </div>

            <div className="md:col-span-2">
              <label className="inline-flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded text-orange-500 focus:ring-orange-500"
                  checked={saveToProfile}
                  onChange={(e) => setSaveToProfile(e.target.checked)}
                />
                {t('Salva questi dati sul profilo per i prossimi acquisti')}
              </label>
            </div>
          </div>

          <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-xs">
            <Shield className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>
              {t('Verrai reindirizzato al portale ufficiale PagoPA per completare il pagamento. StyleForge non vede né salva i dati della tua carta.')}
            </span>
          </div>

          {submitError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex items-center justify-between gap-4 flex-wrap pt-2">
            <div>
              <p className="text-xs text-slate-500 uppercase font-medium">{t('Totale')}</p>
              <p className="text-2xl font-bold text-orange-600">
                {formatEur(selectedPkg.price_cents)}
                <span className="text-sm text-slate-500 font-normal ml-2">
                  · {selectedPkg.credits.toLocaleString('it-IT')} {t('crediti')}
                </span>
              </p>
            </div>
            <button
              type="submit"
              disabled={!canSubmit}
              className="btn btn-primary px-6 py-3 inline-flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" /> {t('Avvio pagamento…')}
                </>
              ) : (
                <>
                  {t('Procedi al pagamento')} <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Footer info */}
      <div className="text-center text-xs text-slate-400 flex items-center justify-center gap-1">
        <Info className="w-3 h-3" />
        {t('Pagamenti elaborati tramite ERSAF · Partner Tecnologico SolutionPA / Intesa Sanpaolo')}
      </div>
    </div>
  );
};

export default BuyCredits;
