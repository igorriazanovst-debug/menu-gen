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
  RecognizedProduct,
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
  // ── photo recognition (OCR + LLM) ──────────────────────────────────────
  const recognizeFileRef = useRef<HTMLInputElement>(null);
  const [recognizeMode, setRecognizeMode] = useState<'single' | 'multi'>('single');
  const [recognizing, setRecognizing] = useState(false);
  const [recognized, setRecognized] = useState<RecognizedProduct[]>([]);
  const [recognizedChecked, setRecognizedChecked] = useState<boolean[]>([]);

  const startRecognize = (mode: 'single' | 'multi') => {
    setRecognizeMode(mode);
    setError(null);
    recognizeFileRef.current?.click();
  };

  const onPhotoChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setRecognizing(true);
    setError(null);
    setRecognized([]);
    try {
      const b64: string = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(new Error('read failed'));
        r.readAsDataURL(file);
      });
      const { data } = await fridgeApi.recognizePhoto(b64, recognizeMode);
      if (recognizeMode === 'single') {
        const prod = (data as any).product as RecognizedProduct | null;
        if (!prod) {
          setError('Продукт не распознан. Заполните вручную.');
        } else {
          applyRecognized(prod);
        }
      } else {
        const list = ((data as any).products ?? []) as RecognizedProduct[];
        if (list.length === 0) {
          setError('Продукты не распознаны. Попробуйте другое фото.');
        }
        setRecognized(list);
        setRecognizedChecked(list.map(() => true));
      }
    } catch (err: any) {
      setError('Ошибка распознавания: ' + (err?.response?.data?.detail || err?.message || ''));
    } finally {
      setRecognizing(false);
    }
  };

  const applyRecognized = (prod: RecognizedProduct) => {
    setName(prod.name);
    setProductId(null);
    if (prod.quantity) {
      const m = prod.quantity.match(/[0-9]+([.,][0-9]+)?/);
      if (m) setQuantity(m[0].replace(',', '.'));
    }
    if (prod.category_slug) {
      const found = categories.find(c => c.slug === prod.category_slug);
      if (found) setSelectedCat(found);
    }
  };

  const addRecognizedBatch = async () => {
    const chosen = recognized.filter((_, i) => recognizedChecked[i]);
    if (chosen.length === 0) return;
    const today = new Date();
    today.setDate(today.getDate() + 7);
    const exp = today.toISOString().slice(0, 10);
    setSubmitting(true);
    setError(null);
    try {
      for (const prod of chosen) {
        let qty = 1;
        if (prod.quantity) {
          const m = prod.quantity.match(/[0-9]+([.,][0-9]+)?/);
          if (m) qty = parseFloat(m[0].replace(',', '.')) || 1;
        }
        const { data } = await fridgeApi.create({
          name: prod.name,
          quantity: qty,
          unit: UNITS[0],
          expiry_date: exp,
          product: null,
          category_slug: prod.category_slug ?? selectedCat?.slug ?? undefined, // MG_B02CAT
        });
        onAdded(data);
      }
      onClose();
    } catch (e: any) {
      setError('Ошибка: ' + (e?.response?.data?.detail || e?.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

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
        category_slug: selectedCat?.slug, // MG_B02CAT
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
                <Button
                  variant="ghost"
                  type="button"
                  className="flex-1"
                  onClick={() => startRecognize('single')}
                  disabled={recognizing || submitting}
                >
                  {recognizing ? 'Распознаю...' : '📸 Фото: 1 продукт'}
                </Button>
                <Button
                  variant="ghost"
                  type="button"
                  className="flex-1"
                  onClick={() => startRecognize('multi')}
                  disabled={recognizing || submitting}
                >
                  {recognizing ? 'Распознаю...' : '📸 Фото: несколько'}
                </Button>
                <input
                  ref={recognizeFileRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={onPhotoChosen}
                />
              </div>

              {recognized.length > 0 && (
                <div data-testid="recognized-list" className="rounded-xl border border-gray-200 p-3 space-y-2">
                  <div className="text-sm font-medium text-chocolate">Распознанные продукты</div>
                  {recognized.map((rp, i) => (
                    <label key={`${rp.name}-${i}`} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={recognizedChecked[i] ?? false}
                        onChange={(ev) => {
                          const next = [...recognizedChecked];
                          next[i] = ev.target.checked;
                          setRecognizedChecked(next);
                        }}
                      />
                      <span className="flex-1">
                        {rp.category_icon ? `${rp.category_icon} ` : ''}{rp.name}
                        {rp.quantity ? ` · ${rp.quantity}` : ''}
                        {` · ${Math.round(rp.confidence * 100)}%`}
                      </span>
                    </label>
                  ))}
                  <Button
                    type="button"
                    className="w-full"
                    onClick={addRecognizedBatch}
                    disabled={submitting}
                  >
                    {submitting ? 'Добавляю...' : 'Добавить выбранные'}
                  </Button>
                </div>
              )}

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
