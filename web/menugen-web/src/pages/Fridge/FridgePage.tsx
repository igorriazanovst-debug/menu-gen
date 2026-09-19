import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Card } from '../../components/ui/Card';
import { PageSpinner } from '../../components/ui/Spinner';
import { Button } from '../../components/ui/Button';
import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';
import { FridgeItemDetailModal } from '../../components/fridge/FridgeItemDetailModal';
import { HistoryEditorModal } from '../../components/fridge/HistoryEditorModal';
import { EditFridgeItemModal } from '../../components/fridge/EditFridgeItemModal'; // MG_B03
import { ConsumeFridgeItemModal } from '../../components/fridge/ConsumeFridgeItemModal'; // MG_WRITEOFF
import type { FridgeItem, ProductCategory } from '../../types';

function daysUntil(d: string | null | undefined): number | null {
  if (!d) return null;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((dt.getTime() - today.getTime()) / 86_400_000);
}

// MG_WRITEOFF: инвентаризация — третий взгляд на тот же холодильник. Группы и
// сроки отвечают на вопрос «что у меня есть», инвентаризация — на другой:
// «что из этого кончилось». Поэтому она не фильтр, а отдельный режим: позиции
// в ней проходят подряд, и каждая уходит из очереди, как только про неё
// сказали. Иначе на третьей строке человек забывает, где остановился.
type ViewMode = 'groups' | 'expiry' | 'inventory';

const EXPIRY_BUCKETS = [
  { key: 'expired', title: 'Просрочено!',                emoji: '❌', color: '#FFCDD2', match: (d: number | null) => d != null && d < 0 },
  { key: 'urgent',  title: 'Съесть в течение 2 дней',    emoji: '⚠️', color: '#FFE0B2', match: (d: number | null) => d != null && d >= 0 && d <= 2 },
  { key: 'soon',    title: 'Подходят к завершению',      emoji: '⏰', color: '#FFF9C4', match: (d: number | null) => d != null && d >= 3 && d <= 7 },
  { key: 'ok',      title: 'Достаточно времени',         emoji: '✅', color: '#C8E6C9', match: (d: number | null) => d == null || d > 7 },
];

export const FridgePage: React.FC = () => {
  const [items, setItems]           = useState<FridgeItem[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [loading, setLoading]       = useState(false);
  const [showAdd, setShowAdd]       = useState(false);
  const [detailId, setDetailId]     = useState<number | null>(null);
  const [editItem, setEditItem]     = useState<FridgeItem | null>(null); // MG_B03
  const [consumeItem, setConsumeItem] = useState<FridgeItem | null>(null); // MG_WRITEOFF
  // MG_WRITEOFF: про эти позиции в текущем проходе инвентаризации уже сказали
  // «есть». Списанные уходят из списка сами — их убирает перезагрузка.
  const [kept, setKept] = useState<Set<number>>(new Set());
  const [consumedCount, setConsumedCount] = useState(0);
  const [viewMode, setViewMode]     = useState<ViewMode>('groups');
  const [showHistory, setShowHistory] = useState(false);

  // MG-610: selection mode for expired bulk delete
  const [selecting, setSelecting]   = useState(false);
  const [selected, setSelected]     = useState<Set<number>>(new Set());

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
    // MG_WRITEOFF: удаление и расход — разные вещи, и человеку это надо
    // сказать прямо: удалённое не вернуть, а списанное можно.
    if (!window.confirm(
      'Удалить продукт из холодильника?\n\n' +
      'Если он съеден — закройте это окно и нажмите «Израсходовал»: такое ' +
      'списание можно отменить.',
    )) return;
    await fridgeApi.delete(id);
    setItems(prev => prev.filter(it => it.id !== id));
  };

  const expiredItems = useMemo(
    () => items.filter(it => { const d = daysUntil(it.expiry_date); return d != null && d < 0; }),
    [items],
  );

  const toggleSel = (id: number) =>
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const exitSelect = () => { setSelecting(false); setSelected(new Set()); };

  const askDropHistory = (count: number, allWord: string): boolean | null => {
    const drop = window.confirm(
      `Удалить ${allWord} (${count} шт.)?\n\n` +
      `Нажмите OK, чтобы также удалить эти продукты из истории добавления.\n` +
      `Нажмите Отмена, чтобы оставить их в истории (мягкое удаление).`,
    );
    return drop;
  };

  const deleteSelected = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    const drop = askDropHistory(ids.length, 'выбранные');
    if (drop === null) return;
    const { data } = await fridgeApi.deleteExpired({ ids, drop_history: drop });
    if (data.deleted > 0) await load();
    exitSelect();
  };

  const deleteAllExpired = async () => {
    if (expiredItems.length === 0) return;
    if (!window.confirm(`Удалить ВСЮ просрочку (${expiredItems.length} шт.)?`)) return;
    const drop = window.confirm(
      'Также удалить эти продукты из истории добавления?\n' +
      'OK — удалить из истории. Отмена — оставить в истории (мягкое удаление).',
    );
    const { data } = await fridgeApi.deleteExpired({ all: true, drop_history: drop });
    if (data.deleted > 0) await load();
    exitSelect();
  };

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
    return keys.map(slug => ({ slug, cat: bySlug.get(slug), items: groups.get(slug)! }));
  }, [items, categories]);

  const groupedByExpiry = useMemo(() => {
    const buckets: { key: string; title: string; emoji: string; color: string; items: FridgeItem[] }[] =
      EXPIRY_BUCKETS.map(b => ({ key: b.key, title: b.title, emoji: b.emoji, color: b.color, items: [] }));
    for (const it of items) {
      const d = daysUntil(it.expiry_date);
      for (let i = 0; i < EXPIRY_BUCKETS.length; i++) {
        if (EXPIRY_BUCKETS[i].match(d)) { buckets[i].items.push(it); break; }
      }
    }
    return buckets.filter(b => b.items.length > 0);
  }, [items]);

  const renderItem = (it: FridgeItem) => {
    const dl = daysUntil(it.expiry_date);
    const expired = dl != null && dl < 0;
    const dlColor =
      dl == null ? 'text-gray-500'
      : dl < 0   ? 'text-red-600'
      : dl <= 2  ? 'text-orange-600'
      : dl <= 7  ? 'text-yellow-700'
                 : 'text-gray-600';
    const selectable = selecting && expired;
    const isSel = selected.has(it.id);
    return (
      <Card
        key={it.id}
        className={
          'p-3 flex gap-3 items-start cursor-pointer hover:shadow-md transition ' +
          (selectable && isSel ? 'ring-2 ring-red-500' : '')
        }
        onClick={() => { selectable ? toggleSel(it.id) : setDetailId(it.id); }}
      >
        {selectable && (
          <input
            type="checkbox"
            checked={isSel}
            onChange={() => toggleSel(it.id)}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 w-4 h-4 accent-red-600"
          />
        )}
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
          <p className="text-sm text-gray-600 mt-0.5">{it.quantity ?? ''} {it.unit ?? ''}</p>
          {it.expiry_date && (
            <p className={`text-xs mt-0.5 ${dlColor}`}>
              {dl != null && dl < 0
                ? `Просрочено ${-dl} дн.`
                : `Срок: ${it.expiry_date}${dl != null ? ` (через ${dl} дн)` : ''}`}
            </p>
          )}
        </div>
        {!selecting && (
          <div className="flex flex-col gap-1">
            {/* MG_WRITEOFF: расход — не удаление; пачку можно початую */}
            <button
              onClick={(e) => { e.stopPropagation(); setConsumeItem(it); }}
              className="text-gray-400 hover:text-primary text-sm"
              title="Израсходовал"
            >➖</button>
            {/* MG_B03: edit */}
            <button
              onClick={(e) => { e.stopPropagation(); setEditItem(it); }}
              className="text-gray-400 hover:text-tomato text-sm"
              title="Редактировать"
            >✎</button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(it.id); }}
              className="text-gray-400 hover:text-red-600 text-sm"
              title="Удалить"
            >🗑</button>
          </div>
        )}
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-chocolate">Холодильник</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setShowHistory(true)}>🕘 История</Button>
          {expiredItems.length > 0 && !selecting && (
            <Button variant="ghost" onClick={() => setSelecting(true)}>
              🧹 Удалить просрочку
            </Button>
          )}
          <Button onClick={() => setShowAdd(true)}>+ Добавить</Button>
        </div>
      </div>

      {selecting && (
        <Card className="p-3 flex items-center gap-2 flex-wrap bg-red-50 border border-red-200">
          <span className="text-sm text-red-700">
            Выберите просроченные продукты ({selected.size} выбрано)
          </span>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={exitSelect}>Отмена</Button>
            <Button onClick={deleteAllExpired}>Удалить всю просрочку</Button>
            <Button onClick={deleteSelected} disabled={selected.size === 0}>
              Удалить выбранные
            </Button>
          </div>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex border-b border-border">
        {([
          { key: 'groups', label: '🗂  По группам' },
          { key: 'expiry', label: '⏱  По сроку годности' },
          { key: 'inventory', label: '📋  Инвентаризация' },
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
          >{t.label}</button>
        ))}
      </div>

      {loading ? (
        <PageSpinner />
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          Холодильник пуст. Нажмите «+ Добавить» чтобы внести продукт.
        </Card>
      ) : viewMode === 'inventory' ? (
        <InventoryList
          items={items.filter(it => !kept.has(it.id))}
          total={items.length}
          consumed={consumedCount}
          onKeep={(id) => setKept(prev => new Set(prev).add(id))}
          onPartly={(it) => setConsumeItem(it)}
          onGone={async (it) => {
            try {
              await fridgeApi.consume(it.id);
              setConsumedCount(c => c + 1);
              await load();
            } catch {
              window.alert('Не удалось списать позицию.');
            }
          }}
        />
      ) : viewMode === 'groups' ? (
        <div className="space-y-4">
          {groupedByCategory.map(grp => {
            const bg = grp.cat?.color ?? '#ECEFF1';
            const name = grp.cat?.name_ru ?? 'Без категории';
            const icon = grp.cat?.icon ?? '📦';
            return (
              <div key={grp.slug} className="rounded-2xl p-3" style={{ backgroundColor: bg }}>
                <div className="flex items-center gap-2 px-2 pb-2">
                  <span className="text-xl">{icon}</span>
                  <span className="font-semibold text-chocolate">{name}</span>
                  <span className="ml-auto bg-surface/70 rounded-full px-2 py-0.5 text-xs font-medium">{grp.items.length}</span>
                </div>
                <div className="bg-surface rounded-xl p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {grp.items.map(renderItem)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-4">
          {groupedByExpiry.map(b => (
            <div key={b.key} className="rounded-2xl p-3" style={{ backgroundColor: b.color }}>
              <div className="flex items-center gap-2 px-2 pb-2">
                <span className="text-xl">{b.emoji}</span>
                <span className="font-semibold text-chocolate">{b.title}</span>
                <span className="ml-auto bg-surface/70 rounded-full px-2 py-0.5 text-xs font-medium">{b.items.length}</span>
              </div>
              <div className="bg-surface rounded-xl p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {b.items.map(renderItem)}
              </div>
            </div>
          ))}
        </div>
      )}

      {detailId != null && (
        <FridgeItemDetailModal itemId={detailId} onClose={() => setDetailId(null)} />
      )}

      {editItem && (
        <EditFridgeItemModal
          item={editItem}
          categories={categories}
          onClose={() => setEditItem(null)}
          onSaved={load}
        />
      )}

      {consumeItem && (
        <ConsumeFridgeItemModal
          item={consumeItem}
          onClose={() => setConsumeItem(null)}
          onDone={() => { setConsumedCount(c => c + 1); load(); }}
        />
      )}

      {showAdd && (
        <AddFridgeItemModal onClose={() => setShowAdd(false)} onAdded={onAdded} />
      )}

      {showHistory && (
        <HistoryEditorModal
          onClose={() => setShowHistory(false)}
          onChanged={load}
        />
      )}
    </div>
  );
};

// ── MG_WRITEOFF: инвентаризация ─────────────────────────────────────────────

interface InventoryListProps {
  items: FridgeItem[];
  total: number;
  consumed: number;
  onKeep: (id: number) => void;
  onPartly: (item: FridgeItem) => void;
  onGone: (item: FridgeItem) => void;
}

/**
 * Проход по холодильнику: три ответа на позицию — «есть», «осталось меньше» и
 * «кончилось». Удаления здесь нет намеренно: инвентаризация про расход, а не
 * про ошибки в списке. Ошибки правятся в обычном виде холодильника.
 */
const InventoryList: React.FC<InventoryListProps> = ({ items, total, consumed, onKeep, onPartly, onGone }) => {
  if (total === 0) {
    return <Card className="p-8 text-center text-gray-500">Холодильник пуст — сверять нечего.</Card>;
  }
  if (items.length === 0) {
    return (
      <Card className="p-8 text-center">
        <div className="text-4xl">📋</div>
        <p className="mt-3 text-chocolate">
          {consumed === 0 ? 'Всё на месте. Холодильник сходится.' : `Готово. Списано позиций: ${consumed}.`}
        </p>
      </Card>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-gray-500 px-1">
        <span>Осталось пройти: {items.length} из {total}</span>
        {consumed > 0 && <span className="text-primary">списано: {consumed}</span>}
      </div>
      {items.map(it => (
        <Card key={it.id} className="p-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-semibold text-chocolate truncate">{it.name}</span>
            <span className="text-sm text-gray-500 whitespace-nowrap">{it.quantity ?? ''} {it.unit ?? ''}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" variant="ghost" onClick={() => onKeep(it.id)}>✓ Есть</Button>
            <Button size="sm" variant="ghost" onClick={() => onPartly(it)}>✎ Осталось меньше</Button>
            <Button size="sm" onClick={() => onGone(it)}>➖ Кончилось</Button>
          </div>
        </Card>
      ))}
    </div>
  );
};
