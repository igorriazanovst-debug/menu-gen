// DIARY_V2 / freemium: ручное добавление — рецепт из базы, продукт из базы, либо вручную.
import React, { useEffect, useRef, useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { diaryApi } from '../../api/diary';
import { recipesApi } from '../../api/recipes';
import { fridgeApi } from '../../api/fridge';
import { getErrorMessage } from '../../utils/api';
import { packageGrams } from '../../utils/packageSize'; // MG_DIARYSCAN
import { MEAL_LABELS } from '../../types';
import type { MealType, Recipe, Product, BarcodeLookupResult } from '../../types';

interface Props {
  date: string;
  memberId?: number;
  onClose: () => void;
  onAdded: () => void;
}

type Mode = 'recipe' | 'product' | 'manual';
type Totals = { calories: number; proteins: number; fats: number; carbs: number };

const MEALS: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack'];

// Прочитать число из string | number | {value} | null.
const toNum = (v: unknown): number => {
  if (v == null) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  if (typeof v === 'string') {
    const n = parseFloat(v.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  }
  if (typeof v === 'object' && 'value' in (v as Record<string, unknown>)) {
    return toNum((v as { value: unknown }).value);
  }
  return 0;
};

const round0 = (n: number) => Math.round(n);
const round1 = (n: number) => Math.round(n * 10) / 10;

// Totals -> nutrition payload в формате {value, unit} (как у ручного ввода).
const totalsToNutrition = (t: Totals) => {
  const n: Record<string, { value: string; unit: string }> = {};
  if (t.calories) n.calories = { value: String(round0(t.calories)), unit: 'ккал' };
  if (t.proteins) n.proteins = { value: String(round1(t.proteins)), unit: 'г' };
  if (t.fats) n.fats = { value: String(round1(t.fats)), unit: 'г' };
  if (t.carbs) n.carbs = { value: String(round1(t.carbs)), unit: 'г' };
  return n;
};

export const AddDiaryEntryModal: React.FC<Props> = ({ date, memberId, onClose, onAdded }) => {
  const [mode, setMode] = useState<Mode>('recipe');
  const [mealType, setMealType] = useState<MealType>('breakfast');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const num = (v: string) => {
    const n = parseFloat(v.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  };

  // ── Manual ────────────────────────────────────────────────────────────────
  // MG_MANUALPROD: КБЖУ вводится НА 100 Г, а съеденное — в граммах. Так же, как
  // во вкладке «Продукт»: пользователь считает КБЖУ один раз, а порции меняются.
  // Раньше поля были «итог за порцию × число порций» — из них нельзя собрать
  // переиспользуемый продукт (в каталоге КБЖУ хранится на 100 г).
  const [name, setName] = useState('');
  const [mGrams, setMGrams] = useState('100'); // съедено, г
  const [cal, setCal] = useState(''); // на 100 г
  const [prot, setProt] = useState('');
  const [fat, setFat] = useState('');
  const [carb, setCarb] = useState('');
  // MG_MANUALPROD: по умолчанию сохраняем продукт в каталог семьи — иначе он
  // нигде потом не ищется (ни в дневнике, ни в холодильнике).
  const [saveToCatalog, setSaveToCatalog] = useState(true);

  // ── Recipe ──────────────────────────────────────────────────────────────
  const [recipeQuery, setRecipeQuery] = useState('');
  const [recipeResults, setRecipeResults] = useState<Recipe[]>([]);
  const [recipeLoading, setRecipeLoading] = useState(false);
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  // 'grams' если у рецепта есть КБЖУ на 100 г; иначе fallback на 'portions'.
  const [recipeUnit, setRecipeUnit] = useState<'grams' | 'portions'>('grams');
  const [recipeAmount, setRecipeAmount] = useState('100');

  // ── Product ─────────────────────────────────────────────────────────────
  const [productQuery, setProductQuery] = useState('');
  const [productResults, setProductResults] = useState<Product[]>([]);
  const [productLoading, setProductLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [productGrams, setProductGrams] = useState('100');
  // MG_DIARYSCAN: в дневник еду вносят упаковками — выпил бутылку йогурта,
  // съел пачку чипсов. Штрих-код избавляет от поиска по названию, а фасовка
  // из справочника подставляет количество.
  const [showScanner, setShowScanner] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanNote, setScanNote] = useState('');
  const scanHandled = useRef(false);

  // Дебаунс-поиск рецептов.
  const recipeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    if (selectedRecipe) return; // выбран — не ищем
    const q = recipeQuery.trim();
    if (q.length < 2) { setRecipeResults([]); return; }
    setRecipeLoading(true);
    clearTimeout(recipeTimer.current);
    recipeTimer.current = setTimeout(async () => {
      try {
        const { data } = await recipesApi.list({ search: q, page_size: 12 });
        setRecipeResults(data.results ?? []);
      } catch {
        setRecipeResults([]);
      } finally {
        setRecipeLoading(false);
      }
    }, 300);
    return () => clearTimeout(recipeTimer.current);
  }, [recipeQuery, selectedRecipe]);

  // Дебаунс-поиск продуктов.
  const productTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    if (selectedProduct) return;
    const q = productQuery.trim();
    if (q.length < 2) { setProductResults([]); return; }
    setProductLoading(true);
    clearTimeout(productTimer.current);
    productTimer.current = setTimeout(async () => {
      try {
        const data = await fridgeApi.searchProducts(q);
        setProductResults(data ?? []);
      } catch {
        setProductResults([]);
      } finally {
        setProductLoading(false);
      }
    }, 300);
    return () => clearTimeout(productTimer.current);
  }, [productQuery, selectedProduct]);

  const pickRecipe = (r: Recipe) => {
    setSelectedRecipe(r);
    setRecipeResults([]);
    const hasPer100 = toNum(r.kcal_per_100g) > 0;
    setRecipeUnit(hasPer100 ? 'grams' : 'portions');
    if (hasPer100) {
      setRecipeAmount(String(r.portion_g && r.portion_g > 0 ? r.portion_g : 100));
    } else {
      setRecipeAmount('1');
    }
  };

  const pickProduct = (p: Product) => {
    setSelectedProduct(p);
    setProductResults([]);
    setProductGrams('100');
    setScanNote('');
  };

  // MG_DIARYSCAN: товар по штрих-коду. Количество берём из фасовки: съели,
  // скорее всего, всю пачку — поправить проще, чем набрать заново.
  const onBarcode = async (detected: { rawValue?: string }[]) => {
    if (scanHandled.current) return;
    const code = detected[0]?.rawValue;
    if (!code) return;
    scanHandled.current = true;
    setShowScanner(false);
    setScanLoading(true);
    setError('');
    try {
      const { data } = await fridgeApi.scanBarcode(code);
      const found = data as BarcodeLookupResult;
      setSelectedProduct({ ...found, id: found.id ?? -1 } as Product);
      setProductResults([]);
      setProductQuery('');
      const grams = packageGrams(found.default_unit) ?? packageGrams(found.name);
      setProductGrams(grams ? String(grams) : '100');

      const hasKbju = toNum(found.calories_per_100g) > 0 || toNum((found.nutrition ?? {}).calories) > 0;
      if (!hasKbju) {
        setScanNote('КБЖУ для этого товара неизвестно — впишите вручную с упаковки.');
      } else if (found.low_confidence) {
        setScanNote('Товара нет в справочниках — данные подобраны ИИ по коду. Проверьте по упаковке.');
      } else {
        setScanNote('');
      }
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      setError(
        status === 404
          ? 'Штрих-код не найден. Найдите продукт по названию или внесите вручную.'
          : getErrorMessage(e),
      );
    } finally {
      setScanLoading(false);
      scanHandled.current = false;
    }
  };

  // ── Подсчёт КБЖУ для предпросмотра/сохранения ───────────────────────────
  const recipeTotals = (): Totals => {
    const r = selectedRecipe;
    if (!r) return { calories: 0, proteins: 0, fats: 0, carbs: 0 };
    if (recipeUnit === 'grams') {
      const f = num(recipeAmount) / 100;
      return {
        calories: toNum(r.kcal_per_100g) * f,
        proteins: toNum(r.proteins_per_100g) * f,
        fats: toNum(r.fats_per_100g) * f,
        carbs: toNum(r.carbs_per_100g) * f,
      };
    }
    // portions: КБЖУ на порцию × число порций
    const p = num(recipeAmount);
    return {
      calories: toNum(r.kcal) * p,
      proteins: toNum(r.proteins) * p,
      fats: toNum(r.fats) * p,
      carbs: toNum(r.carbs) * p,
    };
  };

  // MG_MANUALPROD: КБЖУ на 100 г × съеденные граммы.
  const manualTotals = (): Totals => {
    const f = num(mGrams) / 100;
    return {
      calories: num(cal) * f,
      proteins: num(prot) * f,
      fats: num(fat) * f,
      carbs: num(carb) * f,
    };
  };

  const productTotals = (): Totals => {
    const p = selectedProduct;
    if (!p) return { calories: 0, proteins: 0, fats: 0, carbs: 0 };
    const f = num(productGrams) / 100;
    const n = (p.nutrition ?? {}) as Record<string, unknown>;
    const cal100 = toNum(p.calories_per_100g) || toNum(n.calories);
    return {
      calories: cal100 * f,
      proteins: toNum(n.proteins) * f,
      fats: toNum(n.fats) * f,
      carbs: toNum(n.carbs) * f,
    };
  };

  const save = async () => {
    setSaving(true); setError('');
    try {
      if (mode === 'manual') {
        if (!name.trim()) { setError('Укажите название'); setSaving(false); return; }
        const grams = num(mGrams);
        if (grams <= 0) { setError('Укажите граммовку'); setSaving(false); return; }

        // MG_MANUALPROD: сохранить продукт в каталог семьи, чтобы он находился
        // потом. Best-effort: каталог — премиум-функция, а сам приём пищи
        // (бесплатный) логируем в любом случае, даже если сохранить не вышло.
        if (saveToCatalog) {
          const kbju: Record<string, number> = {};
          if (prot.trim()) kbju.proteins = num(prot);
          if (fat.trim()) kbju.fats = num(fat);
          if (carb.trim()) kbju.carbs = num(carb);
          try {
            await fridgeApi.createProduct({
              name: name.trim(),
              calories_per_100g: cal.trim() ? num(cal) : null,
              nutrition: kbju,
            });
          } catch { /* нет подписки или дубль — не мешаем записи приёма */ }
        }

        await diaryApi.create({
          date, meal_type: mealType,
          custom_name: `${name.trim()}, ${round0(grams)} г`,
          quantity: 1, is_eaten: true,
          nutrition: totalsToNutrition(manualTotals()),
        }, memberId);
      } else if (mode === 'recipe') {
        if (!selectedRecipe) { setError('Выберите рецепт'); setSaving(false); return; }
        const amount = num(recipeAmount);
        if (amount <= 0) { setError('Укажите количество'); setSaving(false); return; }
        const suffix = recipeUnit === 'grams' ? `${round0(amount)} г` : `${amount} порц.`;
        await diaryApi.create({
          date, meal_type: mealType,
          custom_name: `${selectedRecipe.title}, ${suffix}`,
          quantity: 1, is_eaten: true,
          nutrition: totalsToNutrition(recipeTotals()),
        }, memberId);
      } else {
        if (!selectedProduct) { setError('Выберите продукт'); setSaving(false); return; }
        const grams = num(productGrams);
        if (grams <= 0) { setError('Укажите граммовку'); setSaving(false); return; }
        await diaryApi.create({
          date, meal_type: mealType,
          custom_name: `${selectedProduct.name}, ${round0(grams)} г`,
          quantity: 1, is_eaten: true,
          nutrition: totalsToNutrition(productTotals()),
        }, memberId);
      }
      onAdded();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const TabBtn: React.FC<{ m: Mode; label: string }> = ({ m, label }) => (
    <button type="button" onClick={() => { setMode(m); setError(''); }}
      className={`flex-1 px-3 py-2 rounded-xl text-sm font-medium transition ${
        mode === m ? 'bg-tomato text-white' : 'bg-rice text-chocolate'
      }`}>
      {label}
    </button>
  );

  const Preview: React.FC<{ t: Totals }> = ({ t }) => (
    <p className="text-sm text-gray-500 mb-3">
      ≈ {round0(t.calories)} ккал · Б {round1(t.proteins)} · Ж {round1(t.fats)} · У {round1(t.carbs)}
    </p>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
         onClick={onClose}>
      <Card className="w-full max-w-md p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-4">Добавить в дневник</h2>

        <div className="flex gap-2 mb-4">
          <TabBtn m="recipe" label="Рецепт" />
          <TabBtn m="product" label="Продукт" />
          <TabBtn m="manual" label="Вручную" />
        </div>

        <label className="block text-xs text-gray-500 mb-1">Приём пищи</label>
        <div className="flex flex-wrap gap-2 mb-4">
          {MEALS.map((m) => (
            <button key={m} type="button" onClick={() => setMealType(m)}
              className={`px-3 py-1.5 rounded-xl text-sm transition ${
                mealType === m ? 'bg-tomato text-white' : 'bg-rice text-chocolate'
              }`}>
              {MEAL_LABELS[m]}
            </button>
          ))}
        </div>

        {/* ── Recipe ── */}
        {mode === 'recipe' && (
          <div className="mb-4">
            {selectedRecipe ? (
              <div className="flex items-center justify-between gap-2 mb-3 p-2 bg-rice rounded-xl">
                <span className="font-medium text-chocolate truncate">{selectedRecipe.title}</span>
                <button type="button" className="text-gray-400 hover:text-red-600 text-sm shrink-0"
                  onClick={() => { setSelectedRecipe(null); setRecipeQuery(''); }}>сменить</button>
              </div>
            ) : (
              <>
                <label className="block text-xs text-gray-500 mb-1">Поиск рецепта</label>
                <Input value={recipeQuery} onChange={(e) => setRecipeQuery(e.target.value)}
                       placeholder="Введите название (от 2 букв)" />
                {recipeLoading && <p className="text-xs text-gray-400 mt-1">Поиск…</p>}
                {recipeResults.length > 0 && (
                  <div className="mt-1 border border-gray-200 rounded-xl max-h-48 overflow-y-auto">
                    {recipeResults.map((r) => (
                      <button key={r.id} type="button" onClick={() => pickRecipe(r)}
                        className="block w-full text-left px-3 py-2 text-sm hover:bg-rice truncate">
                        {r.title}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}

            {selectedRecipe && (
              <>
                {recipeUnit === 'grams' ? (
                  <>
                    <label className="block text-xs text-gray-500 mb-1">Количество (г)</label>
                    <Input type="number" value={recipeAmount} min="0" step="10"
                           onChange={(e) => setRecipeAmount(e.target.value)} className="mb-3" />
                  </>
                ) : (
                  <>
                    <label className="block text-xs text-gray-500 mb-1">
                      Количество (порций) — у рецепта не задан вес порции
                    </label>
                    <Input type="number" value={recipeAmount} min="0" step="0.5"
                           onChange={(e) => setRecipeAmount(e.target.value)} className="mb-3" />
                  </>
                )}
                <Preview t={recipeTotals()} />
              </>
            )}
          </div>
        )}

        {/* ── Product ── */}
        {mode === 'product' && (
          <div className="mb-4">
            {selectedProduct ? (
              <div className="flex items-center justify-between gap-2 mb-3 p-2 bg-rice rounded-xl">
                <span className="font-medium text-chocolate truncate">{selectedProduct.name}</span>
                <button type="button" className="text-gray-400 hover:text-red-600 text-sm shrink-0"
                  onClick={() => { setSelectedProduct(null); setProductQuery(''); }}>сменить</button>
              </div>
            ) : (
              <>
                <label className="block text-xs text-gray-500 mb-1">Поиск продукта</label>
                <div className="flex gap-2">
                  <Input value={productQuery} onChange={(e) => setProductQuery(e.target.value)}
                         placeholder="Введите название (от 2 букв)" className="flex-1" />
                  {/* MG_DIARYSCAN: упаковку проще отсканировать, чем набрать. */}
                  <Button type="button" variant="ghost" disabled={scanLoading}
                          onClick={() => { scanHandled.current = false; setShowScanner(true); }}>
                    {scanLoading ? '…' : '📷'}
                  </Button>
                </div>
                {productLoading && <p className="text-xs text-gray-400 mt-1">Поиск…</p>}
                {productResults.length > 0 && (
                  <div className="mt-1 border border-gray-200 rounded-xl max-h-48 overflow-y-auto">
                    {productResults.map((p) => (
                      <button key={p.id} type="button" onClick={() => pickProduct(p)}
                        className="block w-full text-left px-3 py-2 text-sm hover:bg-rice truncate">
                        {p.name}
                        {toNum(p.calories_per_100g) > 0 && (
                          <span className="text-gray-400"> · {round0(toNum(p.calories_per_100g))} ккал/100г</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}

            {selectedProduct && (
              <>
                <label className="block text-xs text-gray-500 mb-1">Количество (г)</label>
                <Input type="number" value={productGrams} min="0" step="10"
                       onChange={(e) => setProductGrams(e.target.value)} className="mb-3" />
                {/* MG_DIARYSCAN: что не так с найденным товаром, если не так. */}
                {scanNote && (
                  <div className="text-xs text-amber-700 mb-2">
                    {scanNote}
                    <button type="button" className="ml-2 underline"
                            onClick={() => {
                              setName(selectedProduct.name);
                              setMode('manual');
                              setScanNote('');
                            }}>
                      внести вручную
                    </button>
                  </div>
                )}
                <Preview t={productTotals()} />
              </>
            )}
          </div>
        )}

        {/* ── Manual ── */}
        {mode === 'manual' && (
          <>
            <label className="block text-xs text-gray-500 mb-1">Название</label>
            <Input value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="Например, Копчёная масляная рыба" className="mb-3" />

            {/* MG_MANUALPROD: КБЖУ — на 100 г, чтобы продукт можно было
                переиспользовать и пересчитывать под любую граммовку. */}
            <label className="block text-xs text-gray-500 mb-1">КБЖУ на 100 г</label>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Калории (ккал)</label>
                <Input type="number" value={cal} onChange={(e) => setCal(e.target.value)} min="0" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Белки (г)</label>
                <Input type="number" value={prot} onChange={(e) => setProt(e.target.value)} min="0" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Жиры (г)</label>
                <Input type="number" value={fat} onChange={(e) => setFat(e.target.value)} min="0" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Углеводы (г)</label>
                <Input type="number" value={carb} onChange={(e) => setCarb(e.target.value)} min="0" />
              </div>
            </div>

            <label className="block text-xs text-gray-500 mb-1">Съедено (г)</label>
            <Input type="number" value={mGrams} min="0" step="10"
                   onChange={(e) => setMGrams(e.target.value)} className="mb-3" />

            <label className="flex items-center gap-2 text-sm text-chocolate mb-3 cursor-pointer">
              <input type="checkbox" checked={saveToCatalog}
                     onChange={(e) => setSaveToCatalog(e.target.checked)} />
              Сохранить продукт в каталог (чтобы находить его потом)
            </label>

            <Preview t={manualTotals()} />
          </>
        )}

        {/* MG_DIARYSCAN: камера поверх формы, как в холодильнике. */}
        {showScanner && (
          <div className="mb-4">
            <Scanner onScan={onBarcode} onError={() => setShowScanner(false)} />
            <Button type="button" variant="ghost" className="mt-2"
                    onClick={() => setShowScanner(false)}>Закрыть камеру</Button>
          </div>
        )}

        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Отмена</Button>
          <Button onClick={save} disabled={saving}>{saving ? 'Сохранение…' : 'Добавить'}</Button>
        </div>
      </Card>
    </div>
  );
};
