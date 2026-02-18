import { useState } from 'react';
import { Coins, AlertTriangle, CheckCircle2, X, Sparkles, ArrowRight } from 'lucide-react';

/**
 * Dialog di conferma crediti.
 * Mostra il costo stimato dell'operazione e chiede conferma all'utente.
 *
 * Props:
 * - isOpen: boolean
 * - onConfirm: () => void
 * - onCancel: () => void
 * - operationName: string (es. "Addestramento Modello")
 * - estimatedCredits: number
 * - breakdown: object (dettaglio costi)
 * - currentBalance: number (-1 = infiniti / admin)
 * - loading: boolean (per mostrare spinner durante il caricamento della stima)
 */
const CreditConfirmDialog = ({
  isOpen,
  onConfirm,
  onCancel,
  operationName = 'Operazione',
  estimatedCredits = 0,
  breakdown = {},
  currentBalance = 0,
  loading = false
}) => {
  if (!isOpen) return null;

  const isAdmin = currentBalance === -1;
  const sufficient = isAdmin || currentBalance >= estimatedCredits;
  const balanceAfter = isAdmin ? -1 : currentBalance - estimatedCredits;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div className="relative bg-white rounded-3xl shadow-2xl max-w-md w-full animate-scale-in overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-orange-500 to-orange-600 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                <Coins className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Conferma Crediti</h3>
                <p className="text-sm text-white/80">{operationName}</p>
              </div>
            </div>
            <button
              onClick={onCancel}
              className="p-2 hover:bg-white/20 rounded-xl transition-colors"
            >
              <X className="w-5 h-5 text-white" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="loading-dots text-orange-600">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          ) : (
            <>
              {/* Costo stimato */}
              <div className="bg-orange-50 rounded-2xl p-4 mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-600">Costo stimato</span>
                  <span className="text-2xl font-bold text-orange-600">
                    {estimatedCredits} crediti
                  </span>
                </div>

                {/* Breakdown */}
                {Object.entries(breakdown).map(([key, value]) => {
                  if (key.endsWith('_crediti') || key === 'error') return null;
                  return (
                    <div key={key} className="flex items-center justify-between text-sm text-gray-500 mt-1">
                      <span className="capitalize">{key.replace(/_/g, ' ')}</span>
                      <span>{typeof value === 'number' ? `${value} crediti` : value}</span>
                    </div>
                  );
                })}
              </div>

              {/* Saldo */}
              <div className="space-y-3 mb-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Saldo attuale</span>
                  <span className={`font-bold ${isAdmin ? 'text-green-600' : 'text-gray-900'}`}>
                    {isAdmin ? 'Infinito' : `${currentBalance} crediti`}
                  </span>
                </div>

                {!isAdmin && (
                  <>
                    <div className="flex items-center justify-center">
                      <ArrowRight className="w-4 h-4 text-gray-400" />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Saldo dopo</span>
                      <span className={`font-bold ${balanceAfter >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {balanceAfter >= 0 ? `${balanceAfter} crediti` : 'Insufficiente'}
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Warning se insufficiente */}
              {!sufficient && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-red-800">Crediti insufficienti</p>
                      <p className="text-xs text-red-600 mt-1">
                        Ti mancano {estimatedCredits - currentBalance} crediti per questa operazione.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Admin badge */}
              {isAdmin && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-green-600" />
                    <p className="text-sm text-green-700">
                      Come amministratore, i tuoi crediti sono infiniti.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 btn btn-secondary"
          >
            Annulla
          </button>
          <button
            onClick={onConfirm}
            disabled={!sufficient || loading}
            className="flex-1 btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle2 className="w-4 h-4" />
            Conferma e Procedi
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreditConfirmDialog;
