import { Users, Building2, GraduationCap, Target } from 'lucide-react';

const ThesisAudienceForm = ({ data, onChange, lookupData }) => {
  const handleChange = (field, value) => {
    onChange({ ...data, [field]: value });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Caratteristiche del Pubblico</h2>
        <p className="text-slate-600">Definisci il pubblico target per personalizzare lo stile e il livello di dettaglio.</p>
      </div>

      <div className="card space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Livello di Conoscenza */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <div className="flex items-center gap-2">
                <GraduationCap className="w-4 h-4" />
                Livello di Conoscenza <span className="text-red-500">*</span>
              </div>
            </label>
            <select
              value={data.knowledge_level_id || ''}
              onChange={(e) => handleChange('knowledge_level_id', parseInt(e.target.value) || null)}
              className="input w-full"
              required
            >
              <option value="">Seleziona livello</option>
              {lookupData?.knowledge_levels?.map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </select>
            {data.knowledge_level_id && (
              <p className="text-xs text-slate-500 mt-1">
                {lookupData?.knowledge_levels?.find(l => l.id === data.knowledge_level_id)?.description}
              </p>
            )}
          </div>

          {/* Dimensione Pubblico */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4" />
                Dimensione del Pubblico <span className="text-red-500">*</span>
              </div>
            </label>
            <select
              value={data.audience_size_id || ''}
              onChange={(e) => handleChange('audience_size_id', parseInt(e.target.value) || null)}
              className="input w-full"
              required
            >
              <option value="">Seleziona dimensione</option>
              {lookupData?.audience_sizes?.map((size) => (
                <option key={size.id} value={size.id}>
                  {size.name}
                </option>
              ))}
            </select>
            {data.audience_size_id && (
              <p className="text-xs text-slate-500 mt-1">
                {lookupData?.audience_sizes?.find(s => s.id === data.audience_size_id)?.description}
              </p>
            )}
          </div>

          {/* Industria/Settore */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4" />
                Industria / Settore <span className="text-red-500">*</span>
              </div>
            </label>
            <select
              value={data.industry_id || ''}
              onChange={(e) => handleChange('industry_id', parseInt(e.target.value) || null)}
              className="input w-full"
              required
            >
              <option value="">Seleziona settore</option>
              {lookupData?.industries?.map((industry) => (
                <option key={industry.id} value={industry.id}>
                  {industry.name}
                </option>
              ))}
            </select>
            {data.industry_id && (
              <p className="text-xs text-slate-500 mt-1">
                {lookupData?.industries?.find(i => i.id === data.industry_id)?.description}
              </p>
            )}
          </div>

          {/* Destinatari */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4" />
                Destinatari <span className="text-red-500">*</span>
              </div>
            </label>
            <select
              value={data.target_audience_id || ''}
              onChange={(e) => handleChange('target_audience_id', parseInt(e.target.value) || null)}
              className="input w-full"
              required
            >
              <option value="">Seleziona destinatari</option>
              {lookupData?.target_audiences?.map((audience) => (
                <option key={audience.id} value={audience.id}>
                  {audience.name}
                </option>
              ))}
            </select>
            {data.target_audience_id && (
              <p className="text-xs text-slate-500 mt-1">
                {lookupData?.target_audiences?.find(a => a.id === data.target_audience_id)?.description}
              </p>
            )}
          </div>
        </div>

        {/* Riepilogo */}
        {(data.knowledge_level_id && data.target_audience_id) && (
          <div className="border-t border-slate-200 pt-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Riepilogo Pubblico</h3>
            <div className="p-4 bg-gradient-to-r from-orange-50 to-red-50 border border-orange-200 rounded-lg">
              <p className="text-slate-800">
                Il documento sarà scritto per{' '}
                <strong>
                  {lookupData?.target_audiences?.find(a => a.id === data.target_audience_id)?.name.toLowerCase()}
                </strong>
                {' '}con un livello di conoscenza{' '}
                <strong>
                  {lookupData?.knowledge_levels?.find(l => l.id === data.knowledge_level_id)?.name.toLowerCase()}
                </strong>
                {data.industry_id && (
                  <>
                    {' '}nel settore{' '}
                    <strong>
                      {lookupData?.industries?.find(i => i.id === data.industry_id)?.name.toLowerCase()}
                    </strong>
                  </>
                )}
                .
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ThesisAudienceForm;
