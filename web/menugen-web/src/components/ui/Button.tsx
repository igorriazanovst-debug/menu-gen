import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

// MG_SKIN: варианты на семантических токенах (реагируют на скин)
const variants = {
  primary:   'bg-primary text-primary-fg hover:opacity-90 disabled:opacity-50',
  secondary: 'bg-secondary text-white hover:opacity-90 disabled:opacity-50',
  ghost:     'bg-transparent text-primary hover:bg-primary/10 border border-primary',
  danger:    'bg-danger text-white hover:opacity-90',
};
const sizes = {
  sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2 text-sm', lg: 'px-6 py-3 text-base',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary', size = 'md', loading, children, className = '', disabled, ...rest
}) => (
  <button
    className={[
      'rounded-xl font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40',
      variants[variant], sizes[size], className,
    ].join(' ')}
    disabled={disabled || loading}
    {...rest}
  >
    {loading ? (
      <span className="flex items-center gap-2 justify-center">
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
        Загрузка...
      </span>
    ) : children}
  </button>
);
