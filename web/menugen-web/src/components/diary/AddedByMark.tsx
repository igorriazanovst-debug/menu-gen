// MG_HEADKEEPS: пометка «эту запись внёс не сам человек».
//
// Корона, а не слово «глава»: строка дневника узкая, а знать нужно ровно два
// факта — запись не своя и чья она. Имя уходит в подсказку и в подпись рядом,
// где место позволяет.
//
// Ничего не рисуем, когда автора нет: пустое поле значит «внёс сам», и так у
// всех записей, сделанных до появления этой возможности. Значок у каждой
// строки был бы шумом, за которым потерялось бы исключение.
import React from 'react';

interface Props {
  name?: string | null;
  /** Показать имя рядом с короной — там, где есть место (карточки, не строки). */
  withName?: boolean;
  className?: string;
}

export const AddedByMark: React.FC<Props> = ({ name, withName = false, className = '' }) => {
  if (!name) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] text-amber-600 ${className}`}
      title={`Запись внёс(ла) ${name}`}
    >
      <span aria-hidden>👑</span>
      {withName && <span className="text-gray-500">{name}</span>}
      <span className="sr-only">Запись внёс(ла) {name}</span>
    </span>
  );
};
