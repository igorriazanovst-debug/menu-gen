import React, { useState } from 'react';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { fridgeApi } from '../../api/fridge';
import type { FridgeItem, ProductCategory } from '../../types';

// MG_B03: edit an existing fridge item (name / category / qty / unit / expiry).
const BASE_UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

interface Props {
  item: FridgeItem;
  categories: ProductCategory[];
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}

export const EditFridgeItemModal: React.FC<Props> = ({ item, categories, onClose, onSaved }) => {
  const units = item.unit && !BASE_UNITS.includes(item.unit)
    ? [item.unit, ...BASE_UNITS]
    : BASE_UNITS;

  const [name, setName]       = useState(item.name ?? '');
  const [quantity, setQuantity] = useState(item.quantity != null ? String(item.quantity) : '');
  const [unit, setUnit]       = useState(item.unit || BASE_UNITS[0]);
  const [expiry, setExpiry]   = useState(item.expiry_date ?? '');
  const [slug, setSlug]       = useState<string | null>(item.product_category_slug ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError('Укажите название'); return; }
    const q = parseFloat(quantity.replace(',', '.'));
    if (!quantity || !isFinite(q) || q <= 0) { setError('Укажите количество (> 0)'); return; }
    if (!unit) { setError('Выберите единицу измерения'); return; }
    if (!expiry) { setError('Укажите срок годности'); return; }
    setSubmitting(true);
    try {
      await fridgeApi.update(item.id, {
        name: name.trim(),
        quantity: q,
        unit,
        expiry_date: expiry,
        category_slug: slug ?? undefined,
      });
      await onSaved();
      onClose();
    } catch (err: any) {
      setError('Ошибка: ' + (err?.response?.data?.detail || err?.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-chocolate">Редактировать продукт</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            {/* CATEGORY */}
            <div>
              <label className="text-sm font-medium text-chocolate">Категория</label>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {categories.map(c => {
                  const selected = slug === c.slug;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setSlug(c.slug)}
                      className={
                        'px-2.5 py-1 rounded-full text-xs border transition ' +
                        (selected
                          ? 'border-chocolate ring-2 ring-chocolate/30 font-semibold'
                          : 'border-transparent')
                      }
                      style={{ backgroundColor: c.color || '#ECEFF1' }}
                    >
                      {c.icon ? `${c.icon} ` : ''}{c.name_ru}
                    </button>
                  );
                })}
              </div>
            </div>

            <Input label="Название *" value={name} onChange={(e) => setName(e.target.value)} required />

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Кол-во *"
                type="number"
                step="0.01"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-chocolate">Ед. изм. *</label>
                <select
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  className="rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
                >
                  {units.map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
            </div>

            <Input
              label="Срок годности *"
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              required
            />

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button type="submit" className="w-full" loading={submitting}>Сохранить</Button>
          </form>
        </div>
      </div>
    </div>
  );
};
