// MG_SKIN: круговой индикатор прогресса на токенах. Цвета задаются Tailwind-
// классами stroke-* (по умолчанию stroke-primary / stroke-border), поэтому
// компонент автоматически реагирует на смену скина.
import React from 'react';

interface RingProps {
  /** Заполнение 0..1 */
  value: number;
  size?: number;
  stroke?: number;
  /** Tailwind-класс цвета дуги, напр. stroke-primary */
  colorClass?: string;
  /** Tailwind-класс цвета подложки */
  trackClass?: string;
  children?: React.ReactNode;
  className?: string;
}

export const Ring: React.FC<RingProps> = ({
  value,
  size = 160,
  stroke = 14,
  colorClass = 'stroke-primary',
  trackClass = 'stroke-border',
  children,
  className = '',
}) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  const dash = c * clamped;

  return (
    <div className={`relative inline-flex ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          className={trackClass} strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          className={`${colorClass} transition-[stroke-dasharray] duration-500`}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
        />
      </svg>
      {children && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {children}
        </div>
      )}
    </div>
  );
};
