import { useTranslation } from 'react-i18next';
import NewPasswordCard from '../components/NewPasswordCard';
import { resetPassword } from '../services/api';

const ResetPassword = () => {
  const { t } = useTranslation();
  return (
    <NewPasswordCard
      title={t('Reimposta la password')}
      subtitle={t('Scegli una nuova password per il tuo account.')}
      submitFn={resetPassword}
      successText={t('Password reimpostata. Ora puoi accedere.')}
    />
  );
};

export default ResetPassword;
