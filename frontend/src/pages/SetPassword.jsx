import NewPasswordCard from '../components/NewPasswordCard';
import { setPassword } from '../services/api';

const SetPassword = () => (
  <NewPasswordCard
    title="Imposta la tua password"
    subtitle="Scegli una password per attivare il tuo account StyleForge."
    submitFn={setPassword}
    successText="Account attivato. Ora puoi accedere."
  />
);

export default SetPassword;
