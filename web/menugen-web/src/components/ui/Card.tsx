import React from 'react';

interface CardProps { children: React.ReactNode; className?: string; }

export const Card: React.FC<CardProps> = ({ children, className = '' }) => (
  <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 ${className}`}>
    {children}
  </div>
);
