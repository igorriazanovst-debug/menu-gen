import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = '', id, ...rest }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '_');
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-chocolate">
            {label}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          className={[
            'rounded-xl border px-3 py-2 text-sm outline-none transition',
            'focus:ring-2 focus:ring-tomato/40 focus:border-tomato',
            error ? 'border-red-500' : 'border-gray-300',
            className,
          ].join(' ')}
          {...rest}
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        {hint && !error && <p className="text-xs text-gray-500">{hint}</p>}
      </div>
    );
  },
);
Input.displayName = 'Input';
