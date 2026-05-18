import React from 'react';

// MG_607_V_card: пропускаем все стандартные div-пропы (onClick, style, role и т.д.)
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, className = '', ...rest }) => (
  <div
    className={`bg-white rounded-2xl shadow-sm border border-gray-100 ${className}`}
    {...rest}
  >
    {children}
  </div>
);
