import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Check, Loader, CheckCheck, Inbox } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  getNotifications, getUnreadCount, markNotificationRead, markAllNotificationsRead,
} from '../services/api';

const POLL_MS = 45000;

const timeAgo = (iso, t) => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t('adesso');
  if (m < 60) return t('{{n}} min fa', { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t('{{n}} h fa', { n: h });
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'short' });
};

const NotificationBell = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);

  const refreshCount = useCallback(async () => {
    try {
      const res = await getUnreadCount();
      setUnread(res.unread_count || 0);
    } catch { /* ignora */ }
  }, []);

  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, POLL_MS);
    return () => clearInterval(id);
  }, [refreshCount]);

  // Chiusura al click fuori
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const loadList = async () => {
    setLoading(true);
    try {
      const res = await getNotifications(20);
      setItems(res.notifications || []);
      setUnread(res.unread_count || 0);
    } catch { /* ignora */ } finally {
      setLoading(false);
    }
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) loadList();
  };

  const onItemClick = async (n) => {
    if (!n.is_read) {
      try { await markNotificationRead(n.id); } catch { /* ignora */ }
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
      setUnread((u) => Math.max(0, u - 1));
    }
    if (n.link) { setOpen(false); navigate(n.link); }
  };

  const markAll = async () => {
    try { await markAllNotificationsRead(); } catch { /* ignora */ }
    setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
    setUnread(0);
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="btn btn-ghost relative" title={t('Notifiche')}>
        <Bell className="w-[18px] h-[18px]" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-white rounded-2xl shadow-xl border border-slate-100 z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <span className="font-semibold text-slate-900">{t('Notifiche')}</span>
            {unread > 0 && (
              <button onClick={markAll} className="text-xs text-orange-600 hover:text-orange-700 inline-flex items-center gap-1">
                <CheckCheck className="w-3.5 h-3.5" /> {t('Segna tutte lette')}
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="p-6 flex items-center justify-center gap-2 text-slate-500 text-sm">
                <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
              </div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                <Inbox className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                {t('Nessuna notifica.')}
              </div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => onItemClick(n)}
                  className={`w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors flex gap-3 ${
                    n.is_read ? '' : 'bg-orange-50/40'
                  }`}
                >
                  <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${n.is_read ? 'bg-transparent' : 'bg-orange-500'}`} />
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-medium text-slate-900">{n.title}</span>
                    {n.message && <span className="block text-xs text-slate-500 mt-0.5">{n.message}</span>}
                    <span className="block text-[11px] text-slate-400 mt-1">{timeAgo(n.created_at, t)}</span>
                  </span>
                  {n.is_read && <Check className="w-3.5 h-3.5 text-slate-300 flex-shrink-0 mt-1" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
