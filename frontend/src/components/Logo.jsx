import { Sparkles } from 'lucide-react';

const Logo = ({ size = 'md', className = '' }) => {
  const sizes = {
    sm: 'h-8',
    md: 'h-16',
    lg: 'h-24',
    xl: 'h-32',
  };

  const fallbackSizes = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-20 h-20',
    xl: 'w-32 h-32',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
    xl: 'w-16 h-16',
  };

  return (
    <div className={`inline-block ${className}`}>
      <img
        src="/logo.png"
        alt="StyleForge"
        className={`${sizes[size]} w-auto drop-shadow-2xl`}
        onError={(e) => {
          e.target.style.display = 'none';
          e.target.nextElementSibling.style.display = 'flex';
        }}
      />
      <div className={`hidden ${fallbackSizes[size]} bg-gradient-to-br from-primary-500 to-dark-800 rounded-xl items-center justify-center shadow-2xl`}>
        <Sparkles className={`${iconSizes[size]} text-white`} />
      </div>
    </div>
  );
};

export default Logo;
