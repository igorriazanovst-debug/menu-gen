import React, { useState } from 'react';
import { menuApi } from '../../api/menu';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { fmtWriteOffQty } from '../../utils/writeOffQty';
import type { CookedResult, WriteOffLine } from '../../types';

/**
 * MG_WRITEOFF: что произошло после «Приготовил».
 *
 * Холодильник до сих пор только пополнялся: купленное перекладывалось в него
 * из списка покупок, а убирать приходилось руками. Съеденное оставалось, и на
 * этом расхождении стоит список покупок — он вычитает из потребности то, что
 * лежит дома.
 *
 * Нехватку не додумываем за человека. Раз он отметил, что блюдо приготовлено,
 * значит недостающее он как-то достал, — поэтому там кнопка «Докупил», которая
 * просто закрывает окно, а не заводит ничего в холодильник.
 *
 * Ошибочное нажатие снимается «Отменить списание»: списание — это запись, и
 * вернуть её можно целиком.
 */
interface Props {
  menuId: number;
  itemId: number;
  dishTitle: string;
  result: CookedResult;
  onClose: () => void;
  /** Списание отменили — меню надо перечитать. */
  onUndone: () => void;
}

const Lines: React.FC<{ title: string; icon: string; tone: string; lines: WriteOffLine[] }> = ({
  title, icon, tone, lines,
}) => (
  <div className="mt-4">
    <div className={`flex items-center gap-2 text-sm font-semibold ${tone}`}>
      <span>{icon}</span>
      <span>{title}</span>
    </div>
    <div className="mt-2 space-y-1">
      {lines.map((line, i) => (
        <div key={`${line.name}-${i}`} className="flex items-baseline justify-between gap-3 text-sm">
          <span className="text-chocolate">{line.name}</span>
          <span className="text-gray-500 font-medium whitespace-nowrap">
            {fmtWriteOffQty(line.quantity)} {line.unit}
          </span>
        </div>
      ))}
    </div>
  </div>
);

export const CookedResultModal: React.FC<Props> = ({
  menuId, itemId, dishTitle, result, onClose, onUndone,
}) => {
  const [undoing, setUndoing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUndo = async () => {
    if (undoing) return;
    setUndoing(true);
    setError(null);
    try {
      await menuApi.undoCookItem(menuId, itemId);
      onUndone();
      onClose();
    } catch {
      setUndoing(false);
      setError('Не удалось отменить списание. Попробуйте ещё раз.');
    }
  };

  const written = result.written_off ?? [];
  const missing = result.shortfall ?? [];

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <Card className="max-w-md w-full p-6" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-bold text-chocolate">🍳 {dishTitle}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        {result.created === false && (
          <p className="mt-1 text-xs text-gray-500">
            Блюдо уже было отмечено — второй раз продукты не списались.
          </p>
        )}

        {written.length === 0 && missing.length === 0 && (
          <p className="mt-4 text-sm text-gray-600">
            Списывать было нечего: у блюда не указаны продукты.
          </p>
        )}

        {written.length > 0 && (
          <Lines title="Списано из холодильника" icon="🧊" tone="text-primary" lines={written} />
        )}

        {written.length === 0 && missing.length > 0 && (
          <p className="mt-4 text-sm text-gray-600">
            Из холодильника ничего не списалось — этих продуктов там не было.
          </p>
        )}

        {missing.length > 0 && (
          <Lines title="Не хватило дома" icon="🛒" tone="text-red-600" lines={missing} />
        )}

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex flex-col gap-2">
          <Button onClick={onClose} disabled={undoing}>
            {missing.length === 0 ? 'Готово' : 'Докупил'}
          </Button>
          <button
            type="button"
            onClick={handleUndo}
            disabled={undoing}
            className="text-sm text-gray-500 hover:text-chocolate disabled:opacity-60"
          >
            {undoing ? 'Отменяю…' : '↩ Отменить списание'}
          </button>
        </div>
      </Card>
    </div>
  );
};
