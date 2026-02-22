import { useState, useEffect, useMemo, useRef } from 'react';
import { X, HelpCircle, MessageCircle, ChevronUp, Send, Lightbulb, Clock } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { chatWithCalcifer, getCalciferTip } from '../services/api';

// Import delle immagini di Calcifer
import calcifer1 from '../assets/calcifer/calcifer_1.png';
import calcifer2 from '../assets/calcifer/calcifer_2.png';
import calcifer3 from '../assets/calcifer/calcifer_3.png';
import calcifer4 from '../assets/calcifer/calcifer_4.png';
import calcifer5 from '../assets/calcifer/calcifer_5.png';
import calcifer6 from '../assets/calcifer/calcifer_6.png';
import calcifer7 from '../assets/calcifer/calcifer_7.png';
import calcifer8 from '../assets/calcifer/calcifer_8.png';

const Helper = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(true);
  const [currentTip, setCurrentTip] = useState('');
  const [isChatMode, setIsChatMode] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef(null);
  const location = useLocation();

  // Array di immagini di Calcifer
  const calciferImages = [
    calcifer1, calcifer2, calcifer3, calcifer4,
    calcifer5, calcifer6, calcifer7, calcifer8
  ];

  // Seleziona un'immagine casuale all'avvio
  const randomCalcifer = useMemo(() => {
    const randomIndex = Math.floor(Math.random() * calciferImages.length);
    return calciferImages[randomIndex];
  }, []);

  // Consigli basati sulla pagina corrente
  const tips = {
    '/': [
      'Ciao! Sono Calcifer, il tuo assistente personale di StyleForge! 🔥',
      'Dalla dashboard puoi gestire sessioni, tesi e monitorare i job attivi.',
      'Usa i pulsanti rapidi per accedere a Training, Generazione, Umanizzazione o Tesi.',
      'Ogni sessione addestrata può essere usata per generare contenuti, umanizzare testi o creare tesi.',
      'Prova a chiedermi qualcosa usando la chat! Clicca su "Chatta con me" qui sotto.',
    ],
    '/train': [
      'Qui puoi addestrare una nuova sessione con il tuo stile di scrittura.',
      'Carica un PDF contenente esempi del tuo stile (max 100MB, fino a 500 pagine).',
      'Consiglio: più pagine carichi, migliore sarà l\'apprendimento dello stile!',
      'Il training può richiedere alcuni minuti. Vedrai il progresso nella dashboard.',
      'Una volta completato, potrai generare contenuti, umanizzare testi e creare tesi!',
    ],
    '/generate': [
      'Pronto a creare contenuti con il tuo stile personale! 🔥',
      'Seleziona una sessione già addestrata dal menu a tendina.',
      'Specifica l\'argomento, il numero di parole (100-10.000) e il destinatario.',
      'Il contenuto generato manterrà lo stile che ho imparato dal tuo PDF!',
      'Puoi copiare il risultato negli appunti o scaricarlo come PDF.',
    ],
    '/humanize': [
      'Qui puoi rendere un testo AI non rilevabile dai detector! 🔥',
      'Incolla un testo generato da ChatGPT, Claude o altri AI.',
      'Seleziona una sessione addestrata: il testo verrà riscritto nel tuo stile personale.',
      'Il risultato supera i controlli dei detector AI come GPTZero e altri strumenti di rilevamento.',
      'Funziona aumentando la perplessità e la burstiness per simulare la scrittura umana.',
    ],
    '/thesis': [
      'Benvenuto nel generatore di tesi! Un percorso guidato in 7 step. 🔥',
      'Step 1-2: configura titolo, stile di scrittura, profondità e pubblico.',
      'Step 3: puoi caricare PDF, DOCX o TXT come materiale di riferimento.',
      'Step 4-5: l\'AI genera capitoli e sezioni che puoi modificare prima di confermare.',
      'Step 6-7: il contenuto viene generato e puoi esportare in PDF, DOCX, TXT o Markdown!',
    ],
    'session': [
      'Benvenuto nella pagina di dettaglio della sessione!',
      'Da qui puoi addestrare la sessione caricando un PDF.',
      'Monitora tutti i job di training e generazione associati.',
      'Dopo il training, puoi generare contenuti, umanizzare testi o creare tesi.',
      'Puoi eliminare la sessione quando non ti serve più.',
    ],
  };

  // Determina i suggerimenti in base al percorso
  const getTips = () => {
    if (location.pathname.startsWith('/sessions/')) {
      return tips['session'];
    }
    if (location.pathname.startsWith('/thesis')) {
      return tips['/thesis'];
    }
    return tips[location.pathname] || tips['/'];
  };

  // Cambia il suggerimento quando cambia la pagina
  useEffect(() => {
    const pageTips = getTips();
    setCurrentTip(pageTips[0]);
  }, [location.pathname]);

  // Cambia suggerimento ogni 10 secondi (solo in modalità tips)
  useEffect(() => {
    if (!isOpen || isMinimized || isChatMode) return;

    const pageTips = getTips();
    let currentIndex = 0;

    const interval = setInterval(() => {
      currentIndex = (currentIndex + 1) % pageTips.length;
      setCurrentTip(pageTips[currentIndex]);
    }, 10000);

    return () => clearInterval(interval);
  }, [location.pathname, isOpen, isMinimized, isChatMode]);

  // Scroll automatico alla fine della chat
  useEffect(() => {
    if (isChatMode && chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, isChatMode]);

  // Funzione per inviare un messaggio
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();

    // Aggiungi immediatamente il messaggio dell'utente alla chat
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Svuota l'input DOPO aver aggiunto il messaggio
    setInputMessage('');
    setIsLoading(true);

    try {
      // Crea il contesto dalla pagina corrente
      const context = {
        page: location.pathname,
        pageName: location.pathname === '/' ? 'Dashboard' :
                  location.pathname === '/train' ? 'Training' :
                  location.pathname === '/generate' ? 'Generazione Contenuti' :
                  location.pathname === '/humanize' ? 'Umanizzazione Testi' :
                  location.pathname === '/thesis' ? 'Generazione Tesi' :
                  location.pathname.startsWith('/sessions/') ? 'Dettaglio Sessione' : 'Altra Pagina'
      };

      const response = await chatWithCalcifer(userMessage, 'default', context);

      // Aggiungi la risposta di Calcifer
      setChatMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (error) {
      console.error('Errore nella chat con Calcifer:', error);
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Scusa, ho avuto un problema. Riprova tra poco! 🔥'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleToggle = () => {
    if (!isOpen) {
      setIsOpen(true);
      setIsMinimized(false);
    } else {
      setIsMinimized(!isMinimized);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setIsMinimized(true);
  };

  if (!isOpen) {
    return (
      <button
        onClick={handleToggle}
        className="fixed bottom-6 right-6 w-32 h-32 group z-50"
        title="Ciao! Sono Calcifer, il tuo assistente!"
      >
        <div className="relative w-full h-full transform hover:scale-125 transition-all duration-300 hover:rotate-12 hover:-translate-y-2">
          {/* Glow effect */}
          <div className="absolute inset-0 bg-gradient-to-br from-orange-400 via-yellow-500 to-red-500 rounded-full blur-3xl opacity-80 animate-pulse"></div>

          {/* Ring effect */}
          <div className="absolute inset-0 border-4 border-orange-400 rounded-full animate-ping opacity-75"></div>

          {/* Immagine Calcifer */}
          <img
            src={randomCalcifer}
            alt="Calcifer"
            className="relative w-full h-full object-contain drop-shadow-2xl animate-pulse filter hover:brightness-110"
          />
        </div>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* Mascotte */}
      <div className="relative">
        {/* Balloon di testo o Chat */}
        {!isMinimized && (
          <div className="absolute bottom-24 right-0 w-[420px] bg-gradient-to-br from-white to-orange-50 rounded-3xl shadow-2xl mb-2 animate-slide-up max-h-[520px] flex flex-col border-2 border-orange-200">
            <div className="absolute bottom-0 right-12 w-0 h-0 border-l-[12px] border-l-transparent border-r-[12px] border-r-transparent border-t-[12px] border-t-orange-200 transform translate-y-full"></div>
            <div className="absolute bottom-0 right-12 w-0 h-0 border-l-[10px] border-l-transparent border-r-[10px] border-r-transparent border-t-[10px] border-t-white transform translate-y-[11px] translate-x-[1px]"></div>

            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b-2 border-orange-200 bg-gradient-to-r from-orange-100 to-yellow-100 rounded-t-3xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-red-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
                  <span className="text-2xl">🔥</span>
                </div>
                <div>
                  <span className="font-bold text-slate-900 text-lg block">Calcifer</span>
                  <span className="text-xs text-slate-600">Il tuo assistente magico</span>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setIsChatMode(!isChatMode)}
                  className={`p-2.5 rounded-xl transition-all shadow-md ${
                    isChatMode
                      ? 'bg-gradient-to-br from-primary-500 to-primary-600 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                  title={isChatMode ? 'Mostra consigli' : 'Chatta con me'}
                >
                  {isChatMode ? <Lightbulb className="w-5 h-5" /> : <MessageCircle className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Contenuto */}
            {!isChatMode ? (
              // Modalità Consigli
              <div className="p-5">
                <div className="bg-gradient-to-br from-orange-50 to-yellow-50 border-2 border-orange-200 rounded-2xl p-4 mb-4 shadow-inner">
                  <p className="text-slate-800 text-sm leading-relaxed font-medium">
                    {currentTip}
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleClose}
                    className="flex-1 text-sm px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 rounded-xl transition-all shadow-md hover:shadow-lg border-2 border-slate-200 font-semibold"
                  >
                    Nascondi
                  </button>
                  <button
                    onClick={() => {
                      const pageTips = getTips();
                      const currentIndex = pageTips.indexOf(currentTip);
                      const nextIndex = (currentIndex + 1) % pageTips.length;
                      setCurrentTip(pageTips[nextIndex]);
                    }}
                    className="flex-1 text-sm px-4 py-2.5 bg-gradient-to-r from-orange-400 to-red-500 hover:from-orange-500 hover:to-red-600 text-white rounded-xl transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 font-semibold"
                  >
                    <HelpCircle className="w-4 h-4" />
                    Altro consiglio
                  </button>
                </div>
              </div>
            ) : (
              // Modalità Chat
              <>
                <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[320px] bg-white">
                  {chatMessages.length === 0 ? (
                    <div className="text-center text-slate-500 text-sm py-8">
                      <div className="w-16 h-16 mx-auto mb-3 bg-gradient-to-br from-orange-200 to-red-300 rounded-full flex items-center justify-center">
                        <MessageCircle className="w-8 h-8 text-orange-600" />
                      </div>
                      <p className="font-semibold text-slate-700">Chiedimi qualsiasi cosa su StyleForge!</p>
                      <p className="text-xs mt-2 text-orange-600 font-medium">Sono qui per aiutarti 🔥</p>
                    </div>
                  ) : (
                    chatMessages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm shadow-md ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-br from-primary-600 to-primary-700 text-white'
                              : 'bg-gradient-to-br from-orange-50 to-yellow-50 text-slate-800 border-2 border-orange-200'
                          }`}
                        >
                          {msg.content}
                        </div>
                      </div>
                    ))
                  )}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-gradient-to-br from-orange-50 to-yellow-50 border-2 border-orange-200 px-4 py-3 rounded-2xl shadow-md">
                        <div className="flex gap-1">
                          <span className="w-2 h-2 bg-orange-500 rounded-full animate-bounce"></span>
                          <span className="w-2 h-2 bg-orange-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></span>
                          <span className="w-2 h-2 bg-orange-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Input Chat */}
                <div className="p-4 border-t-2 border-orange-200 bg-gradient-to-r from-orange-50 to-yellow-50">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Scrivi un messaggio..."
                      className="flex-1 px-4 py-2.5 text-sm border-2 border-orange-200 rounded-xl focus:outline-none focus:border-primary-500 shadow-sm"
                      disabled={isLoading}
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={isLoading || !inputMessage.trim()}
                      className="px-4 py-2.5 bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-xl hover:from-primary-700 hover:to-primary-800 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Avatar mascotte - Calcifer */}
        <button
          onClick={handleToggle}
          className="w-32 h-32 group relative"
          title="Clicca per aprire/chiudere"
        >
          <div className="relative w-full h-full transform hover:scale-125 transition-all duration-300 hover:rotate-12 hover:-translate-y-2">
            {/* Glow effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-orange-400 via-yellow-500 to-red-500 rounded-full blur-3xl opacity-80 animate-pulse"></div>

            {/* Ring effect on hover */}
            <div className="absolute inset-0 border-4 border-orange-400 rounded-full group-hover:animate-ping opacity-0 group-hover:opacity-75"></div>

            {/* Immagine Calcifer */}
            <img
              src={randomCalcifer}
              alt="Calcifer"
              className="relative w-full h-full object-contain drop-shadow-2xl"
            />
          </div>
        </button>
      </div>
    </div>
  );
};

export default Helper;
