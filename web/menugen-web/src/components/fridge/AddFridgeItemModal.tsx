import React, { useEffect, useRef, useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { fridgeApi } from '../../api/fridge';
import type {
  BarcodeLookupResult,
  FridgeHistoryItem,
  FridgeItem,
  Product,
  ProductCategory,
} from '../../types';

const UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

interface Props {
  onClose: () => void;
  onAdded: (item: FridgeItem) => void;
}

export const AddFridgeItemModal: React.FC<Props> = ({ onClose, onAdded }) => {
  const [name, setName]           = useState('');
  const [quantity, setQuantity]   = useState('');
  const [unit, setUnit]           = useState(UNITS[0]);
  const [expiry, setExpiry]       = useState('');
  const [productId, setProductId] = useState<number | null>(null);
  const [imageUrl, setImageUrl]   = useState<string | null>(null);
  const [showScanner, setShowScanner] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const handledRef = useRef(false);
  // MG-610 focus refs
  const nameRef = useRef<HTMLInputElement>(null);
  const qtyRef = useRef<HTMLInputElement>(null);
  const unitRef = useRef<HTMLSelectElement>(null);
  const expiryRef = useRef<HTMLInputElement>(null);
  const catRef = useRef<HTMLDivElement>(null);
  const focusInvalid = (el: HTMLElement | null) => {
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (typeof (el as any).focus === 'function') (el as any).focus();
  };

  // MG-609
  const [categories, setCategories]       = useState<ProductCategory[]>([]);
  const [history, setHistory]             = useState<FridgeHistoryItem[]>([]);
  const [selectedCat, setSelectedCat]     = useState<ProductCategory | null>(null);
  const [seedProducts, setSeedProducts]   = useState<Product[]>([]);
  const [metaLoading, setMetaLoading]     = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setMetaLoading(true);
      try {
        const [catsRes, histRes] = await Promise.all([
          fridgeApi.categories().catch(() => ({ data: [] as ProductCategory[] })),
          fridgeApi.history(40).catch(() => ({ data: [] as FridgeHistoryItem[] })),
        ]);
        if (cancelled) return;
        setCategories((catsRes as any).data ?? []);
        setHistory((histRes as any).data ?? []);
      } finally {
        if (!cancelled) setMetaLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedCat) { setSeedProducts([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await fridgeApi.products({ category: selectedCat.slug, seed: true });
        if (!cancelled) setSeedProducts(data ?? []);
      } catch {
        if (!cancelled) setSeedProducts([]);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedCat]);

  const applyHistory = (h: FridgeHistoryItem) => {
    setName(h.name);
    setProductId(h.product_id);
    if (h.image_url) setImageUrl(h.image_url);
    if (h.default_unit && UNITS.includes(h.default_unit)) setUnit(h.default_unit);
    if (h.category_slug) {
      const found = categories.find(c => c.slug === h.category_slug);
      if (found) setSelectedCat(found);
    }
  };

  const applySeed = (p: Product) => {
    setName(p.name);
    setProductId(p.id);
    if (p.image_url) setImageUrl(p.image_url);
    if (p.default_unit && UNITS.includes(p.default_unit)) setUnit(p.default_unit);
  };

  const onBarcodeDetected = async (detected: { rawValue?: string }[]) => {
    if (handledRef.current) return;
    const code = detected[0]?.rawValue;
    if (!code) return;
    handledRef.current = true;
    setShowScanner(false);
    setScanLoading(true);
    setError(null);
    try {
      const { data } = await fridgeApi.scanBarcode(code);
      const p = data as BarcodeLookupResult;
      setName(p.name);
      setProductId(p.id);
      if (p.image_url) setImageUrl(p.image_url);
      if (p.default_unit && UNITS.includes(p.default_unit)) setUnit(p.default_unit);
      if (p.category_slug) {
        const found = categories.find(c => c.slug === p.category_slug);
        if (found) setSelectedCat(found);
      }
    } catch (e: any) {
      if (e?.response?.status === 404) {
        setError('Штрих-код не найден. Заполните поля вручную.');
        setName(`Штрих-код ${code}`);
      } else {
        setError('Ошибка поиска: ' + (e?.response?.data?.detail || e?.message || ''));
      }
    } finally {
      setScanLoading(false);
      handledRef.current = false;
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!selectedCat) {
      setError('Выберите категорию');
      focusInvalid(catRef.current);
      return;
    }
    if (!name.trim()) {
      setError('Укажите название');
      focusInvalid(nameRef.current);
      return;
    }
    const q = parseFloat(quantity.replace(',', '.'));
    if (!quantity || !isFinite(q) || q <= 0) {
      setError('Укажите количество (> 0)');
      focusInvalid(qtyRef.current);
      return;
    }
    if (!unit) {
      setError('Выберите единицу измерения');
      focusInvalid(unitRef.current);
      return;
    }
    if (!expiry) {
      setError('Укажите срок годности');
      focusInvalid(expiryRef.current);
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await fridgeApi.create({
        name: name.trim(),
        quantity: q,
        unit,
        expiry_date: expiry,
        product: productId,
      });
      onAdded(data);
      onClose();
    } catch (e: any) {
      setError('Ошибка: ' + (e?.response?.data?.detail || e?.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-chocolate">Добавить в холодильник</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {showScanner ? (
            <div className="space-y-3">
              <div className="rounded-xl overflow-hidden border border-gray-200">
                <Scanner
                  onScan={onBarcodeDetected}
                  styles={{ container: { width: '100%' } }}
                  scanDelay={300}
                />
              </div>
              <Button variant="ghost" className="w-full" onClick={() => setShowScanner(false)}>
                Отмена
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              {/* HISTORY */}
              {history.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-chocolate">Из истории</label>
                  <div className="mt-1 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                    {history.map((h, i) => (
                      <button
                        key={`${h.name}-${i}`}
                        type="button"
                        onClick={() => applyHistory(h)}
                        className="px-2.5 py-1 rounded-full bg-rice border border-gray-200 text-xs hover:bg-tomato/10"
                      >
                        {h.category_icon ? `${h.category_icon} ` : ''}{h.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* CATEGORY */}
              <div>
                <label className="text-sm font-medium text-chocolate">Категория *</label>
                {metaLoading ? (
                  <div className="mt-1 h-8 rounded bg-gray-100 animate-pulse" />
                ) : (
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {categories.map(c => {
                      const selected = selectedCat?.id === c.id;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => setSelectedCat(c)}
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
                )}
              </div>

              {/* SEED PRODUCTS for selected category */}
              {selectedCat && seedProducts.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-chocolate">Базовые продукты</label>
                  <div className="mt-1 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                    {seedProducts.map(p => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => applySeed(p)}
                        className="px-2.5 py-1 rounded-full bg-white border border-gray-300 text-xs hover:bg-rice"
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  type="button"
                  className="flex-1"
                  onClick={() => { handledRef.current = false; setShowScanner(true); }}
                  disabled={scanLoading}
                >
                  {scanLoading ? 'Поиск...' : '📷 Сканировать штрих-код'}
                </Button>
              </div>

              {imageUrl && (
                <img src={imageUrl} alt="" className="max-h-32 mx-auto rounded-lg object-contain"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              )}

              <Input
                label="Название *"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />

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
                    {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
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

              <Button type="submit" className="w-full" loading={submitting}>
                Добавить
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
