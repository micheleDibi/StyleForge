import { Check, Settings, Users, Paperclip, List, FileText, Sparkles, Download, BookMarked, Brain } from 'lucide-react';

const STEPS = [
  { num: 1, label: 'Parametri', icon: Settings },
  { num: 2, label: 'Pubblico', icon: Users },
  { num: 3, label: 'Allegati', icon: Paperclip },
  { num: 4, label: 'Paper', icon: BookMarked },
  { num: 5, label: 'Knowledge Base', icon: Brain },
  { num: 6, label: 'Capitoli', icon: List },
  { num: 7, label: 'Sezioni', icon: FileText },
  { num: 8, label: 'Generazione', icon: Sparkles },
  { num: 9, label: 'Download', icon: Download }
];

const StepIndicator = ({ currentStep, totalSteps = STEPS.length }) => {
  return (
    <div className="mb-8 md:pb-10">
      <div className="flex items-center justify-between">
        {STEPS.slice(0, totalSteps).map((step, idx) => (
          <div key={step.num} className="flex items-center flex-1">
            <div className="relative flex flex-col items-center">
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300
                ${currentStep > step.num
                  ? 'bg-green-500 text-white shadow-lg shadow-green-500/30'
                  : currentStep === step.num
                    ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg shadow-orange-500/30 scale-110'
                    : 'bg-slate-200 text-slate-500'}
              `}>
                {currentStep > step.num ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <step.icon className="w-5 h-5" />
                )}
              </div>
              <span className={`
                hidden md:block absolute top-full mt-2 text-[11px] font-medium text-center leading-tight
                whitespace-nowrap pointer-events-none
                ${currentStep >= step.num ? 'text-slate-900' : 'text-slate-400'}
              `}>
                {step.label}
              </span>
            </div>

            {idx < totalSteps - 1 && (
              <div className={`
                flex-1 h-1 mx-1.5 md:mx-2 rounded-full transition-all duration-300
                ${currentStep > step.num ? 'bg-green-500' : 'bg-slate-200'}
              `} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default StepIndicator;
