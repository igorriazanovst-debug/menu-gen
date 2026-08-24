// MG_MYPRODUCTS: продукты семьи — посмотреть, поправить, удалить.
//
// Заводить свои продукты стало легко (галочка в дневнике включена по
// умолчанию), а управлять ими было негде: опечатку в названии не исправить,
// ошибку в КБЖУ не поправить, лишнее не удалить. Этот экран закрывает ровно то.
//
// Каталожные продукты сюда не попадают: их правит только админка, и сервер
// откажет, даже если запрос как-то дойдёт (см. _guard_own во вьюхе).
import React, { useCallback, useEffect, useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { fridgeApi } from '../../api/fridge';
import { getErrorMessage } from '../../utils/api';
import type { Product, ProductCategory } from '../../types';

const toNum = (v: unknown): number => {
  if (v == null) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  const n = parseFloat(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
};

const num = (v: string) => {
  const n = parseFloat(v.replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
};

type Draft = {
  name: string;
  cal: string;
  prot: string;
  fat: string;
  carb: string;
  categoryId: number | null;
};

const draftOf = (p: Product): Draft => {
  const n = (p.nutrition ?? {}) as Record<string, unknown>;
  const s = (v: unknown) => (v == null || v === '' ? '' : String(toNum(v)));
  return {
    name: p.name,
    cal: p.calories_per_100g == null ? '' : String(toNum(p.calories_per_100g)),
    prot: s(n.proteins),
    fat: s(n.fats),
    carb: s(n.carbs),
    categoryId: p.category_id ?? null,
  };
};

export const MyProductsPage: React.FC = () => {
  const [items, setItems] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [prods, cats] = await Promise.all([
        fridgeApi.products({ own: true }),
        fridgeApi.categories().catch(() => ({ data: [] as ProductCategory[] })),
      ]);
      setItems(prods.data ?? []);
      setCategories((cats as { data: ProductCategory[] }).data ?? []);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const startEdit = (p: Product) => {
    setEditingId(p.id);
    setDraft(draftOf(p));
    setError('');
  };

  const cancelEdit = () => { setEditingId(null); setDraft(null); };

  const save = async () => {
    if (!draft || editingId == null) return;
    if (!draft.name.trim()) { setError('Укажите название'); return; }
    setBusy(true);
    setError('');
    try {
      // КБЖУ пишем только заполненное: пустое поле означает «неизвестно», а не
      // «ноль». Ноль в дневнике выглядел бы как факт.
      const kbju: Record<string, number> = {};
      if (draft.prot.trim()) kbju.proteins = num(draft.prot);
      if (draft.fat.trim()) kbju.fats = num(draft.fat);
      if (draft.carb.trim()) kbju.carbs = num(draft.carb);
      await fridgeApi.updateProduct(editingId, {
        name: draft.name.trim(),
        calories_per_100g: draft.cal.trim() ? num(draft.cal) : null,
        nutrition: kbju,
        category_id: draft.categoryId,
      });
      cancelEdit();
      await load();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (p: Product) => {
    // Позиции холодильника переживут удаление (FK стоит SET_NULL), но потеряют
    // связь с КБЖУ и категорией — об этом честно предупреждаем.
    const used = p.fridge_usage ?? 0;
    const warn = used > 0
      ? `\n\nНа продукт ссылается позиций в холодильнике: ${used}. Они останутся, но потеряют КБЖУ и категорию.`
      : '';
    if (!window.confirm(`Удалить «${p.name}»?${warn}`)) return;
    setBusy(true);
    setError('');
    try {
      await fridgeApi.deleteProduct(p.id);
      await load();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const kbjuLine = (p: Product) => {
    const n = (p.nutrition ?? {}) as Record<string, unknown>;
    const cal = toNum(p.calories_per_100g);
    if (!cal && !n.proteins && !n.fats && !n.carbs) return 'КБЖУ не указано';
    return `${Math.round(cal)} ккал · Б ${toNum(n.proteins)} · Ж ${toNum(n.fats)} · У ${toNum(n.carbs)} (на 100 г)`;
  };

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-chocolate mb-1">Мои продукты</h1>
      <p className="text-sm text-gray-500 mb-4">
        Продукты вашей семьи — те, что вы завели вручную или из дневника.
        Общий каталог правится только через поддержку.
      </p>

      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-gray-400 text-sm">Загрузка…</p>
      ) : items.length === 0 ? (
        <Card className="p-6 text-center text-gray-500 text-sm">
          Своих продуктов пока нет. Они появляются, когда вы вносите продукт
          вручную в дневник и оставляете галочку «Сохранить продукт в каталог».
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((p) => (
            <Card key={p.id} className="p-4">
              {editingId === p.id && draft ? (
                <div className="space-y-3">
                  <Input
                    label="Название"
                    value={draft.name}
                    onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  />
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">КБЖУ на 100 г</label>
                    <div className="grid grid-cols-2 gap-3">
                      <Input type="number" min="0" placeholder="ккал" value={draft.cal}
                             onChange={(e) => setDraft({ ...draft, cal: e.target.value })} />
                      <Input type="number" min="0" placeholder="белки" value={draft.prot}
                             onChange={(e) => setDraft({ ...draft, prot: e.target.value })} />
                      <Input type="number" min="0" placeholder="жиры" value={draft.fat}
                             onChange={(e) => setDraft({ ...draft, fat: e.target.value })} />
                      <Input type="number" min="0" placeholder="углеводы" value={draft.carb}
                             onChange={(e) => setDraft({ ...draft, carb: e.target.value })} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Категория</label>
                    <div className="flex flex-wrap gap-1.5">
                      {categories.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => setDraft({
                            ...draft,
                            categoryId: draft.categoryId === c.id ? null : c.id,
                          })}
                          className={
                            'px-2.5 py-1 rounded-full text-xs border transition ' +
                            (draft.categoryId === c.id
                              ? 'border-chocolate ring-2 ring-chocolate/30 font-semibold'
                              : 'border-transparent')
                          }
                          style={{ backgroundColor: c.color || '#ECEFF1' }}
                        >
                          {c.icon ? `${c.icon} ` : ''}{c.name_ru}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" onClick={cancelEdit} disabled={busy}>Отмена</Button>
                    <Button onClick={save} disabled={busy}>{busy ? 'Сохранение…' : 'Сохранить'}</Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-chocolate truncate">
                      {p.category_icon ? `${p.category_icon} ` : ''}{p.name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{kbjuLine(p)}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {p.category_name || 'Без категории'}
                      {(p.fridge_usage ?? 0) > 0 && ` · в холодильнике: ${p.fridge_usage}`}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button variant="ghost" onClick={() => startEdit(p)} disabled={busy}>Править</Button>
                    <button
                      type="button"
                      onClick={() => remove(p)}
                      disabled={busy}
                      className="text-sm text-gray-400 hover:text-red-600 px-2"
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
