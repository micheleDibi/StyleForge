import { useTranslation } from 'react-i18next';
import NewPasswordCard from '../components/NewPasswordCard';
import { setPassword } from '../services/api';

const SetPassword = () => {
  const { t } = useTranslation();
  return (
    <NewPasswordCard
      title={t('Imposta la tua password')}
      subtitle={t('Scegli una password per attivare il tuo account StyleForge.')}
      submitFn={setPassword}
      successText={t('Account attivato. Ora puoi accedere.')}
    />
  );
};

export default SetPassword;
