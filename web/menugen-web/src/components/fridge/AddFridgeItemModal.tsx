import React, { useState, useRef } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { fridgeApi } from '../../api/fridge';
import type { BarcodeLookupResult, FridgeItem } from '../../types';

const UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

interface Props {
  onClose: () => void;
  onAdded: (item: FridgeItem) => void;
}

export const AddFridgeItemModal: React.FC<Props> = ({ onClose, onAdded }) => {
  const [name, setName]         = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit]         = useState(UNITS[0]);
  const [expiry, setExpiry]     = useState('');
  const [productId, setProductId] = useState<number | null>(null);
  const [imageUrl, setImageUrl]   = useState<string | null>(null);
  const [showScanner, setShowScanner] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const handledRef = useRef(false);

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
    if (!name.trim() || !quantity || !unit || !expiry) {
      setError('Заполните все обязательные поля');
      return;
    }
    const q = parseFloat(quantity.replace(',', '.'));
    if (!isFinite(q) || q <= 0) { setError('Кол-во должно быть > 0'); return; }
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
