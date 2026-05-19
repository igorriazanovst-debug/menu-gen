import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Card } from '../../components/ui/Card';
import { PageSpinner } from '../../components/ui/Spinner';
import { Button } from '../../components/ui/Button';
import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';
import { FridgeItemDetailModal } from '../../components/fridge/FridgeItemDetailModal';
import type { FridgeItem, ProductCategory } from '../../types';

function daysUntil(d: string | null | undefined): number | null {
  if (!d) return null;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((dt.getTime() - today.getTime()) / 86_400_000);
}

type ViewMode = 'groups' | 'expiry';

const EXPIRY_BUCKETS = [
  {
    key: 'expired',
    title: 'Просрочено!',
    emoji: '❌',
    color: '#FFCDD2',
    match: (d: number | null) => d != null && d < 0,
  },
  {
    key: 'urgent',
    title: 'Съесть в течение 2 дней',
    emoji: '⚠️',
    color: '#FFE0B2',
    match: (d: number | null) => d != null && d >= 0 && d <= 2,
  },
  {
    key: 'soon',
    title: 'Подходят к завершению',
    emoji: '⏰',
    color: '#FFF9C4',
    match: (d: number | null) => d != null && d >= 3 && d <= 7,
  },
  {
    key: 'ok',
    title: 'Достаточно времени',
    emoji: '✅',
    color: '#C8E6C9',
    match: (d: number | null) => d == null || d > 7,
  },
];

export const FridgePage: React.FC = () => {
  const [items, setItems]           = useState<FridgeItem[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [loading, setLoading]       = useState(false);
  const [showAdd, setShowAdd]       = useState(false);
  const [detailId, setDetailId]     = useState<number | null>(null);
  const [viewMode, setViewMode]     = useState<ViewMode>('groups');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [itemsRes, catsRes] = await Promise.all([
        fridgeApi.list(),
        fridgeApi.categories().catch(() => ({ data: [] as ProductCategory[] })),
      ]);
      setItems(itemsRes.data.results ?? []);
      setCategories((catsRes as any).data ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onAdded = (item: FridgeItem) => setItems(prev => [item, ...prev]);

  const onDelete = async (id: number) => {
    if (!window.confirm('Удалить продукт?')) return;
    await fridgeApi.delete(id);
    setItems(prev => prev.filter(it => it.id !== id));
  };

  // ── Grouped by category ──
  const groupedByCategory = useMemo(() => {
    const bySlug = new Map<string, ProductCategory>();
    categories.forEach(c => bySlug.set(c.slug, c));
    const groups = new Map<string, FridgeItem[]>();
    for (const it of items) {
      const slug = (it.product_category_slug ?? '').trim() || 'other';
      const arr = groups.get(slug) ?? [];
      arr.push(it);
      groups.set(slug, arr);
    }
    const keys = Array.from(groups.keys()).sort((a, b) => {
      const ao = bySlug.get(a)?.sort_order ?? 9999;
      const bo = bySlug.get(b)?.sort_order ?? 9999;
      return ao - bo;
    });
    return keys.map(slug => ({
      slug,
      cat: bySlug.get(slug),
      items: groups.get(slug)!,
    }));
  }, [items, categories]);

  // ── Grouped by expiry bucket ──
  const groupedByExpiry = useMemo(() => {
    const buckets: { key: string; title: string; emoji: string; color: string; items: FridgeItem[] }[] =
      EXPIRY_BUCKETS.map(b => ({ key: b.key, title: b.title, emoji: b.emoji, color: b.color, items: [] }));
    for (const it of items) {
      const d = daysUntil(it.expiry_date);
      for (let i = 0; i < EXPIRY_BUCKETS.length; i++) {
        if (EXPIRY_BUCKETS[i].match(d)) {
          buckets[i].items.push(it);
          break;
        }
      }
    }
    return buckets.filter(b => b.items.length > 0);
  }, [items]);

  const renderItem = (it: FridgeItem) => {
    const dl = daysUntil(it.expiry_date);
    const dlColor =
      dl == null ? 'text-gray-500'
      : dl < 0   ? 'text-red-600'
      : dl <= 2  ? 'text-orange-600'
      : dl <= 7  ? 'text-yellow-700'
                 : 'text-gray-600';
    return (
      <Card
        key={it.id}
        className="p-3 flex gap-3 items-start cursor-pointer hover:shadow-md transition"
        onClick={() => setDetailId(it.id)}
      >
        {it.product_image_url ? (
          <img
            src={it.product_image_url}
            alt=""
            className="w-12 h-12 rounded-lg object-cover bg-gray-50"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        ) : (
          <div className="w-12 h-12 rounded-lg bg-rice flex items-center justify-center text-xl">
            {it.product_category_icon || '📦'}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-chocolate truncate">{it.name}</h3>
          <p className="text-sm text-gray-600 mt-0.5">
            {it.quantity ?? ''} {it.unit ?? ''}
          </p>
          {it.expiry_date && (
            <p className={`text-xs mt-0.5 ${dlColor}`}>
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
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Холодильник</h1>
        <Button onClick={() => setShowAdd(true)}>+ Добавить</Button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {([
          { key: 'groups', label: '🗂  По группам' },
          { key: 'expiry', label: '⏱  По сроку годности' },
        ] as { key: ViewMode; label: string }[]).map(t => (
          <button
            key={t.key}
            onClick={() => setViewMode(t.key)}
            className={
              'px-4 py-2 text-sm font-semibold border-b-2 transition ' +
              (viewMode === t.key
                ? 'border-tomato text-tomato'
                : 'border-transparent text-gray-500 hover:text-chocolate')
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <PageSpinner />
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          Холодильник пуст. Нажмите «+ Добавить» чтобы внести продукт.
        </Card>
      ) : viewMode === 'groups' ? (
        <div className="space-y-4">
          {groupedByCategory.map(grp => {
            const bg = grp.cat?.color ?? '#ECEFF1';
            const name = grp.cat?.name_ru ?? 'Без категории';
            const icon = grp.cat?.icon ?? '📦';
            return (
              <div
                key={grp.slug}
                className="rounded-2xl p-3"
                style={{ backgroundColor: bg }}
              >
                <div className="flex items-center gap-2 px-2 pb-2">
                  <span className="text-xl">{icon}</span>
                  <span className="font-semibold text-chocolate">{name}</span>
                  <span className="ml-auto bg-white/70 rounded-full px-2 py-0.5 text-xs font-medium">
                    {grp.items.length}
                  </span>
                </div>
                <div className="bg-white rounded-xl p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {grp.items.map(renderItem)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-4">
          {groupedByExpiry.map(b => (
            <div
              key={b.key}
              className="rounded-2xl p-3"
              style={{ backgroundColor: b.color }}
            >
              <div className="flex items-center gap-2 px-2 pb-2">
                <span className="text-xl">{b.emoji}</span>
                <span className="font-semibold text-chocolate">{b.title}</span>
                <span className="ml-auto bg-white/70 rounded-full px-2 py-0.5 text-xs font-medium">
                  {b.items.length}
                </span>
              </div>
              <div className="bg-white rounded-xl p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {b.items.map(renderItem)}
              </div>
            </div>
          ))}
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
