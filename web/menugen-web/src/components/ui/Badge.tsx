import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  color?: 'red' | 'green' | 'yellow' | 'gray' | 'blue';
}

const colors = {
  red:    'bg-red-100 text-red-700',
  green:  'bg-green-100 text-green-700',
  yellow: 'bg-yellow-100 text-yellow-700',
  gray:   'bg-gray-100 text-gray-600',
  blue:   'bg-blue-100 text-blue-700',
};

export const Badge: React.FC<BadgeProps> = ({ children, color = 'gray' }) => (
  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[color]}`}>
    {children}
  </span>
);
