import React, { useEffect, useState, useCallback } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Card } from '../../components/ui/Card';
import { PageSpinner } from '../../components/ui/Spinner';
import { Button } from '../../components/ui/Button';
import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';
import { FridgeItemDetailModal } from '../../components/fridge/FridgeItemDetailModal';
import type { FridgeItem } from '../../types';

function daysUntil(d: string | null | undefined): number | null {
  if (!d) return null;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((dt.getTime() - today.getTime()) / 86_400_000);
}

export const FridgePage: React.FC = () => {
  const [items, setItems]     = useState<FridgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await fridgeApi.list();
      setItems(data.results ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onAdded = (item: FridgeItem) => {
    setItems(prev => [item, ...prev]);
  };

  const onDelete = async (id: number) => {
    if (!window.confirm('Удалить продукт?')) return;
    await fridgeApi.delete(id);
    setItems(prev => prev.filter(it => it.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Холодильник</h1>
        <Button onClick={() => setShowAdd(true)}>+ Добавить</Button>
      </div>

      {loading ? <PageSpinner /> : items.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          Холодильник пуст. Нажмите «+ Добавить» чтобы внести продукт.
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map(it => {
            const dl = daysUntil(it.expiry_date);
            const dlColor = dl == null ? 'text-gray-500'
              : dl < 0 ? 'text-red-600'
              : dl < 3 ? 'text-yellow-600' : 'text-gray-600';
            return (
              <Card key={it.id} className="p-4 flex gap-3 items-start cursor-pointer hover:shadow-md transition" onClick={() => setDetailId(it.id)}>
                {it.product_image_url ? (
                  <img src={it.product_image_url} alt=""
                    className="w-14 h-14 rounded-lg object-cover bg-gray-50"
                    onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                ) : (
                  <div className="w-14 h-14 rounded-lg bg-rice flex items-center justify-center text-2xl">📦</div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-chocolate truncate">{it.name}</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {it.quantity ?? ''} {it.unit ?? ''}
                  </p>
                  {it.expiry_date && (
                    <p className={`text-xs mt-1 ${dlColor}`}>
                      {dl != null && dl < 0
                        ? `Просрочено ${-dl} дн.`
                        : `Срок: ${it.expiry_date}${dl != null ? ` (через ${dl} дн)` : ''}`}
                    </p>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(it.id); }}
                  className="text-gray-400 hover:text-red-600 text-sm"
                  title="Удалить"
                >
                  🗑
                </button>
              </Card>
            );
          })}
        </div>
      )}

      {detailId != null && (
        <FridgeItemDetailModal
          itemId={detailId}
          onClose={() => setDetailId(null)}
        />
      )}

      {showAdd && (
        <AddFridgeItemModal
          onClose={() => setShowAdd(false)}
          onAdded={onAdded}
        />
      )}
    </div>
  );
};
