import NewPasswordCard from '../components/NewPasswordCard';
import { resetPassword } from '../services/api';

const ResetPassword = () => (
  <NewPasswordCard
    title="Reimposta la password"
    subtitle="Scegli una nuova password per il tuo account."
    submitFn={resetPassword}
    successText="Password reimpostata. Ora puoi accedere."
  />
);

export default ResetPassword;
