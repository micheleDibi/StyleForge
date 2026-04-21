import { useState, useEffect, useMemo, useRef } from 'react';
import { X, MessageCircle, Send, Lightbulb, ChevronDown } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { chatWithCalcifer } from '../services/api';

// Import delle immagini di Calcifer
import calcifer1 from '../assets/calcifer/calcifer_1.png';
import calcifer2 from '../assets/calcifer/calcifer_2.png';
import calcifer3 from '../assets/calcifer/calcifer_3.png';
import calcifer4 from '../assets/calcifer/calcifer_4.png';
import calcifer5 from '../assets/calcifer/calcifer_5.png';
import calcifer6 from '../assets/calcifer/calcifer_6.png';
import calcifer7 from '../assets/calcifer/calcifer_7.png';
import calcifer8 from '../assets/calcifer/calcifer_8.png';

// Nomi pagine leggibili
const PAGE_NAMES = {
  '/': 'Dashboard',
  '/train': 'Addestramento',
  '/generate': 'Generazione Contenuti',
  '/humanize': 'Umanizzazione Testi',
  '/thesis': 'Generazione Tesi',
  '/enhance-image': 'Migliora Immagine',
  '/carousel': 'Carosello Instagram',
  '/research': 'Ricerca Accademica',
  '/admin': 'Pannello Admin',
};

const getPageName = (pathname) => {
  if (pathname.startsWith('/sessions/')) return 'Dettaglio Sessione';
  if (pathname.startsWith('/thesis')) return 'Generazione Tesi';
  return PAGE_NAMES[pathname] || 'StyleForge';
};

// Suggerimenti rapidi per pagina
const QUICK_SUGGESTIONS = {
  '/': ['Come funziona StyleForge?', 'Come inizio un addestramento?', 'Cosa posso fare dalla dashboard?'],
  '/train': ['Che tipo di PDF devo caricare?', 'Quanto dura il training?', 'Posso addestrare piu volte?'],
  '/generate': ['Come scelgo la sessione giusta?', 'Quante parole posso generare?', 'Come scarico il risultato?'],
  '/humanize': ['Che differenza tra Correzione e Umanizzazione?', 'Serve una sessione addestrata?', 'Come funziona la Correzione Anti-AI?'],
  '/thesis': ['Come funziona il generatore di tesi?', 'Posso allegare materiale di riferimento?', 'In quali formati posso esportare?'],
  '/research': ['Come funziona la ricerca accademica?', 'Quali fonti posso interrogare?', 'Come genero un riassunto di un paper?'],
};

const getQuickSuggestions = (pathname) => {
  if (pathname.startsWith('/sessions/')) return ['Cosa posso fare con questa sessione?', 'Come genero contenuti?'];
  if (pathname.startsWith('/thesis')) return QUICK_SUGGESTIONS['/thesis'];
  return QUICK_SUGGESTIONS[pathname] || QUICK_SUGGESTIONS['/'];
};

// Renderizza markdown leggero (bold, italic)
const renderMessage = (text) => {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
};

const Helper = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const chatContainerRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const location = useLocation();

  const calciferImages = [calcifer1, calcifer2, calcifer3, calcifer4, calcifer5, calcifer6, calcifer7, calcifer8];
  const randomCalcifer = useMemo(() => calciferImages[Math.floor(Math.random() * calciferImages.length)], []);

  // Messaggio di benvenuto quando si apre la chat
  useEffect(() => {
    if (isOpen && chatMessages.length === 0) {
      const pageName = getPageName(location.pathname);
      setChatMessages([{
        role: 'assistant',
        content: `Ciao! Sono Calcifer, il tuo assistente. Sei nella pagina **${pageName}**. Come posso aiutarti?`
      }]);
    }
  }, [isOpen]);

  // Scroll automatico alla fine della chat
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, isLoading]);

  // Rileva scroll per mostrare bottone "scroll to bottom"
  const handleScroll = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setShowScrollBtn(!isNearBottom);
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Focus input quando si apre
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current.focus(), 300);
    }
  }, [isOpen]);

  const handleSendMessage = async (messageText) => {
    const text = (messageText || inputMessage).trim();
    if (!text || isLoading) return;

    setChatMessages(prev => [...prev, { role: 'user', content: text }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const context = {
        page: location.pathname,
        pageName: getPageName(location.pathname),
      };

      const response = await chatWithCalcifer(text, 'default', context);
      setChatMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (error) {
      console.error('Errore Calcifer:', error);
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Mi dispiace, ho avuto un problema tecnico. Riprova tra poco!'
      }]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleToggle = () => setIsOpen(!isOpen);
  const handleClose = () => setIsOpen(false);

  const pageName = getPageName(location.pathname);
  const suggestions = getQuickSuggestions(location.pathname);

  // Bottone Calcifer (chiuso)
  if (!isOpen) {
    return (
      <button
        onClick={handleToggle}
        className="fixed bottom-6 right-6 w-24 h-24 group z-50"
        title="Ciao! Sono Calcifer, il tuo assistente!"
      >
        <div className="relative w-full h-full transform hover:scale-110 transition-all duration-300 hover:-translate-y-1">
          {/* Glow statico */}
          <div className="absolute inset-2 bg-gradient-to-br from-orange-400/40 via-yellow-500/30 to-red-500/40 rounded-full blur-2xl"></div>
          <img
            src={randomCalcifer}
            alt="Calcifer"
            className="relative w-full h-full object-contain drop-shadow-xl filter hover:brightness-110 transition-all"
          />
        </div>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* Chat Panel */}
      <div className="absolute bottom-28 right-0 w-[400px] bg-white rounded-2xl shadow-2xl animate-slide-up flex flex-col border border-slate-200 overflow-hidden" style={{ maxHeight: 'min(520px, calc(100vh - 180px))' }}>

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-orange-50 to-amber-50 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-orange-400 to-red-500 rounded-full flex items-center justify-center shadow-sm">
              <span className="text-lg">🔥</span>
            </div>
            <div>
              <span className="font-bold text-slate-900 text-sm block leading-tight">Calcifer</span>
              <span className="text-[10px] text-slate-500">{pageName}</span>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div
          ref={chatContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-slate-50"
          style={{ minHeight: '200px' }}
        >
          {chatMessages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center flex-shrink-0 mr-2 mt-1 shadow-sm">
                  <span className="text-xs">🔥</span>
                </div>
              )}
              <div
                className={`max-w-[80%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-orange-500 text-white rounded-br-md'
                    : 'bg-white text-slate-800 border border-slate-200 rounded-bl-md shadow-sm'
                }`}
              >
                {renderMessage(msg.content)}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center flex-shrink-0 mr-2 mt-1 shadow-sm">
                <span className="text-xs">🔥</span>
              </div>
              <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-orange-400 rounded-full animate-bounce"></span>
                  <span className="w-2 h-2 bg-orange-400 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></span>
                  <span className="w-2 h-2 bg-orange-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></span>
                </div>
              </div>
            </div>
          )}

          {/* Quick suggestions (solo all'inizio) */}
          {chatMessages.length <= 1 && !isLoading && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSendMessage(s)}
                  className="text-xs px-3 py-1.5 bg-white border border-orange-200 text-orange-700 rounded-full hover:bg-orange-50 hover:border-orange-300 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-[68px] left-1/2 -translate-x-1/2 bg-white border border-slate-200 shadow-md rounded-full p-1.5 hover:bg-slate-50 transition-colors z-10"
          >
            <ChevronDown className="w-4 h-4 text-slate-500" />
          </button>
        )}

        {/* Input */}
        <div className="px-3 py-2.5 border-t border-slate-200 bg-white flex-shrink-0">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Scrivi un messaggio..."
              className="flex-1 px-3.5 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-400/30 bg-slate-50"
              disabled={isLoading}
              maxLength={500}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isLoading || !inputMessage.trim()}
              className="px-3.5 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Mascotte avatar */}
      <button
        onClick={handleToggle}
        className="w-24 h-24 group relative"
        title="Clicca per chiudere"
      >
        <div className="relative w-full h-full transform hover:scale-110 transition-all duration-300 hover:-translate-y-1">
          <div className="absolute inset-2 bg-gradient-to-br from-orange-400/40 via-yellow-500/30 to-red-500/40 rounded-full blur-2xl"></div>
          <img
            src={randomCalcifer}
            alt="Calcifer"
            className="relative w-full h-full object-contain drop-shadow-xl"
          />
        </div>
      </button>
    </div>
  );
};

export default Helper;
