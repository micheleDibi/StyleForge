import { useTranslation } from 'react-i18next';
import HierarchyManager from '../components/HierarchyManager';

// Dashboard distributore: gestisce rivenditori e privati del proprio sottoalbero.
const Distributor = () => {
  const { t } = useTranslation();
  return (
    <HierarchyManager
      title={t('Dashboard Distributore')}
      subtitle={t('Gestisci i tuoi rivenditori e privati')}
      allowedChildTypes={['rivenditore', 'privato']}
    />
  );
};

export default Distributor;
