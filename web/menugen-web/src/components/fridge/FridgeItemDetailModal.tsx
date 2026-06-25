import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fridgeApi } from '../../api/fridge';
import { Spinner } from '../ui/Spinner';
import type { FridgeItemDetailsResponse } from '../../types';

interface Props {
  itemId: number;
  onClose: () => void;
}

const fmtNum = (v: any): string => {
  if (v == null) return '—';
  if (typeof v === 'number') return v % 1 === 0 ? String(v) : v.toFixed(1);
  return String(v);
};

export const FridgeItemDetailModal: React.FC<Props> = ({ itemId, onClose }) => {
  const [data, setData] = useState<FridgeItemDetailsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { data } = await fridgeApi.details(itemId);
        if (!cancelled) setData(data);
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || e?.message || 'Ошибка');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [itemId]);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-bold text-chocolate">Карточка продукта</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {loading && <div className="flex justify-center py-8"><Spinner size="lg" /></div>}
          {error && <p className="text-red-600">{error}</p>}

          {data && (() => {
            const { item, product, days_left, usage_30d } = data;
            const imageUrl = item.product_image_url || product?.image_url;
            const nutrition = product?.nutrition || {};
            const daysColor =
              days_left == null ? 'text-gray-500'
              : days_left < 0 ? 'text-red-600'
              : days_left < 3 ? 'text-yellow-600' : 'text-green-700';

            return (
              <div className="space-y-5">
                {/* Header */}
                <div className="flex gap-4">
                  {imageUrl ? (
                    <img src={imageUrl} alt="" className="w-24 h-24 rounded-xl object-cover bg-gray-50"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                  ) : (
                    <div className="w-24 h-24 rounded-xl bg-rice flex items-center justify-center text-4xl">📦</div>
                  )}
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-chocolate">{item.name}</h3>
                    {product?.category && (
                      <p className="text-sm text-gray-500 mt-1">{product.category}</p>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-500">Остаток</p>
                    <p className="font-semibold text-chocolate">
                      {item.quantity ?? '—'} {item.unit ?? ''}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-500">Срок годности</p>
                    <p className={`font-semibold ${daysColor}`}>
                      {days_left == null ? '—'
                        : days_left < 0 ? `Просрочено ${-days_left} дн.`
                        : `${days_left} дн.`}
                    </p>
                    {item.expiry_date && (
                      <p className="text-xs text-gray-400 mt-0.5">до {item.expiry_date}</p>
                    )}
                  </div>
                </div>

                {/* KBJU */}
                <div>
                  <h4 className="font-semibold mb-2 text-chocolate">Пищевая ценность (на 100 г)</h4>
                  {!product ? (
                    <p className="text-sm text-gray-400 italic">— нет данных</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Ккал: <b>{fmtNum(product.calories_per_100g)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Белки: <b>{fmtNum(nutrition.proteins)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Жиры: <b>{fmtNum(nutrition.fats)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Углеводы: <b>{fmtNum(nutrition.carbs)}</b>
                      </span>
                      {nutrition.fiber != null && (
                        <span className="px-3 py-1 bg-rice rounded-full text-sm">
                          Клетч.: <b>{fmtNum(nutrition.fiber)}</b>
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Usage */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="font-semibold text-chocolate">Использование в меню</h4>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      usage_30d.count > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      за 30 дн: {usage_30d.count}
                    </span>
                  </div>
                  {usage_30d.recipes.length === 0 ? (
                    <p className="text-sm text-gray-400 italic">
                      Этот продукт не появлялся в меню за последние 30 дней.
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {usage_30d.recipes.map(r => (
                        <li key={r.recipe_id}
                            className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                            onClick={() => { onClose(); navigate(`/recipes?id=${r.recipe_id}`); }}>
                          <span className="text-sm">🍽 {r.title}</span>
                          <span className="text-sm font-semibold text-tomato">×{r.times}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};
