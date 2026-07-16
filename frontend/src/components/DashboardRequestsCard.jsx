import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Inbox, Send, ChevronRight, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { getMyCreditRequests, getRequestsInbox, getAdminCreditRequests } from '../services/api';

const STATUS_LABELS = {
  pending: 'In attesa',
  approved: 'Approvata',
  rejected: 'Rifiutata',
  canceled: 'Annullata',
};

// Card "Richieste" della dashboard, adattata al ruolo:
//  - approvatori (distributore/rivenditore/admin): richieste da gestire + link
//  - richiedenti (tutti tranne admin): le proprie richieste e il loro stato
const DashboardRequestsCard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAdmin, isManager, isDistributor } = useAuth();

  const [toHandle, setToHandle] = useState(0);
  const [myPending, setMyPending] = useState(0);
  const [lastStatus, setLastStatus] = useState(null);

  useEffect(() => {
    const tasks = [];
    if (isAdmin) {
      tasks.push(getAdminCreditRequests().then((r) => setToHandle(r.total || 0)).catch(() => {}));
    } else if (isManager) {
      tasks.push(getRequestsInbox().then((r) => setToHandle(r.total || 0)).catch(() => {}));
    }
    if (!isAdmin) {
      tasks.push(getMyCreditRequests().then((r) => {
        const reqs = r.requests || [];
        setMyPending(reqs.filter((x) => x.status === 'pending').length);
        setLastStatus(reqs[0]?.status || null);
      }).catch(() => {}));
    }
    Promise.all(tasks);
  }, [isAdmin, isManager]);

  const managerLink = isAdmin ? '/admin' : (isDistributor ? '/distributor' : '/reseller');
  const showHandle = isAdmin || isManager;

  return (
    <div className="glass rounded-2xl p-5">
      <h3 className="font-bold text-slate-900 mb-3 flex items-center gap-2">
        <Inbox className="w-5 h-5 text-orange-500" />
        {t('Richieste crediti')}
      </h3>

      <div className="space-y-2">
        {showHandle && (
          <button
            onClick={() => navigate(managerLink)}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all text-left"
          >
            <Inbox className="w-5 h-5 text-orange-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900">{t('Richieste da gestire')}</p>
              <p className="text-xs text-slate-500">
                {toHandle > 0 ? t('{{n}} in attesa di approvazione', { n: toHandle }) : t('Nessuna in attesa')}
              </p>
            </div>
            {toHandle > 0 && (
              <span className="min-w-[22px] h-[22px] px-1.5 rounded-full bg-red-500 text-white text-xs font-bold flex items-center justify-center">{toHandle}</span>
            )}
            <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
          </button>
        )}

        {!isAdmin && (
          <button
            onClick={() => navigate('/credits/buy')}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 hover:border-orange-300 hover:bg-orange-50/40 transition-all text-left"
          >
            <Send className="w-5 h-5 text-orange-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900">{t('Le mie richieste')}</p>
              <p className="text-xs text-slate-500 flex items-center gap-1">
                {myPending > 0 ? (
                  <><Clock className="w-3 h-3" /> {t('{{n}} in attesa', { n: myPending })}</>
                ) : lastStatus === 'approved' ? (
                  <><CheckCircle2 className="w-3 h-3 text-emerald-500" /> {t('Ultima: approvata')}</>
                ) : lastStatus === 'rejected' ? (
                  <><XCircle className="w-3 h-3 text-red-500" /> {t('Ultima: rifiutata')}</>
                ) : (
                  t('Richiedi crediti al tuo referente')
                )}
              </p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
          </button>
        )}
      </div>
    </div>
  );
};

export default DashboardRequestsCard;
