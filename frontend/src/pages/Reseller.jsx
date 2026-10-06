import { useTranslation } from 'react-i18next';
import HierarchyManager from '../components/HierarchyManager';

// Dashboard rivenditore: gestisce i propri privati.
const Reseller = () => {
  const { t } = useTranslation();
  return (
    <HierarchyManager
      title={t('Dashboard Rivenditore')}
      subtitle={t('Gestisci i tuoi privati')}
      allowedChildTypes={['privato']}
    />
  );
};

export default Reseller;
