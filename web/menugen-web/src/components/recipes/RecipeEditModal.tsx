import React, { useRef, useState } from 'react';
import { recipesApi } from '../../api/recipes';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { getErrorMessage } from '../../utils/api';
import type { Recipe, FoodGroup, ProteinType, GrainType, SuitableMeal } from '../../types';

interface Props {
  recipe: Recipe;
  onClose: () => void;
  onSaved: (r: Recipe) => void;
}

type NutritionKey = 'calories' | 'proteins' | 'fats' | 'carbs' | 'fiber' | 'weight';

const NUTRITION_LABELS: { key: NutritionKey; label: string; unit: string }[] = [
  { key: 'calories', label: 'Калории',    unit: 'ккал' },
  { key: 'proteins', label: 'Белки',      unit: 'г' },
  { key: 'fats',     label: 'Жиры',       unit: 'г' },
  { key: 'carbs',    label: 'Углеводы',   unit: 'г' },
  { key: 'fiber',    label: 'Клетчатка',  unit: 'г' },
  { key: 'weight',   label: 'Вес порции', unit: 'г' },
];

const FOOD_GROUP_OPTIONS: { value: FoodGroup; label: string }[] = [
  { value: 'grain',     label: 'Зерновые / крупы' },
  { value: 'protein',   label: 'Белки (мясо/рыба/яйца/бобовые)' },
  { value: 'vegetable', label: 'Овощи' },
  { value: 'fruit',     label: 'Фрукты' },
  { value: 'dairy',     label: 'Молочные' },
  { value: 'oil',       label: 'Масла / жиры' },
  { value: 'other',     label: 'Прочее' },
];

const PROTEIN_TYPE_OPTIONS: { value: ProteinType; label: string }[] = [
  { value: 'animal', label: 'Животный' },
  { value: 'plant',  label: 'Растительный' },
  { value: 'mixed',  label: 'Смешанный' },
];

const GRAIN_TYPE_OPTIONS: { value: GrainType; label: string }[] = [
  { value: 'whole',   label: 'Цельнозерновые' },
  { value: 'refined', label: 'Рафинированные' },
];

const SUITABLE_FOR_OPTIONS: { value: SuitableMeal; label: string }[] = [
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch',     label: 'Обед' },
  { value: 'dinner',    label: 'Ужин' },
  { value: 'snack',     label: 'Перекус' },
];

export const RecipeEditModal: React.FC<Props> = ({ recipe, onClose, onSaved }) => {
  const [title,      setTitle]      = useState(recipe.title);
  const [cookTime,   setCookTime]   = useState(recipe.cook_time ?? '');
  const [servings,   setServings]   = useState(String(recipe.servings ?? ''));
  const [country,    setCountry]    = useState(recipe.country ?? '');
  const [imageUrl,   setImageUrl]   = useState(recipe.image_url ?? '');
  const [videoUrl,   setVideoUrl]   = useState(recipe.video_url ?? '');
  const [categories, setCategories] = useState((recipe.categories ?? []).join(', '));
  const [nutrition,  setNutrition]  = useState<Record<string, string>>(() => {
    const n = recipe.nutrition ?? {};
    const result: Record<string, string> = {};
    NUTRITION_LABELS.forEach(({ key }) => {
      result[key] = (n as any)[key]?.value ?? '';
    });
    return result;
  });
  const [ingredients,  setIngredients]  = useState(JSON.stringify(recipe.ingredients ?? [], null, 2));
  const [steps,        setSteps]        = useState(JSON.stringify(recipe.steps ?? [], null, 2));

  // Классификация
  const [foodGroup,    setFoodGroup]    = useState<FoodGroup | ''>((recipe.food_group ?? '') as FoodGroup | '');
  const [proteinType,  setProteinType]  = useState<ProteinType | ''>((recipe.protein_type ?? '') as ProteinType | '');
  const [grainType,    setGrainType]    = useState<GrainType | ''>((recipe.grain_type ?? '') as GrainType | '');
  const [suitableFor,  setSuitableFor]  = useState<SuitableMeal[]>(recipe.suitable_for ?? []);
  const [isFattyFish,  setIsFattyFish]  = useState<boolean>(recipe.is_fatty_fish ?? false);
  const [isRedMeat,    setIsRedMeat]    = useState<boolean>(recipe.is_red_meat ?? false);

  const [saving,       setSaving]       = useState(false);
  const [uploadingImg, setUploadingImg] = useState(false);
  const [uploadingVid, setUploadingVid] = useState(false);
  const [error,        setError]        = useState('');
  const [tab,          setTab]          = useState<'basic' | 'nutrition' | 'classification' | 'ingredients' | 'steps'>('basic');

  const imgInputRef = useRef<HTMLInputElement>(null);
  const vidInputRef = useRef<HTMLInputElement>(null);

  const toggleSuitable = (v: SuitableMeal) => {
    setSuitableFor(prev => prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v]);
  };

  const handleUpload = async (file: File, type: 'image' | 'video') => {
    const setUploading = type === 'image' ? setUploadingImg : setUploadingVid;
    setUploading(true);
    setError('');
    try {
      const { data } = await recipesApi.uploadMedia(file, 'image');
      if (type === 'image') setImageUrl(data.url);
      else                  setVideoUrl(data.url);
    } catch (e) {
      setError(getErrorMessage(e) || String(e));
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      let parsedIngredients: any;
      let parsedSteps: any;
      try { parsedIngredients = JSON.parse(ingredients); }
      catch { throw new Error('Ингредиенты — некорректный JSON'); }
      try { parsedSteps = JSON.parse(steps); }
      catch { throw new Error('Шаги — некорректный JSON'); }

      const nutritionPayload: Record<string, { value: string; unit: string }> = {};
      NUTRITION_LABELS.forEach(({ key, unit }) => {
        const v = (nutrition[key] ?? '').trim();
        if (v !== '') nutritionPayload[key] = { value: v, unit: key === 'calories' ? 'ккал' : unit };
      });

      const payload: any = {
        title:       title.trim(),
        cook_time:   cookTime  || undefined,
        servings:    servings ? Number(servings) : undefined,
        country:     country   || undefined,
        image_url:   imageUrl  || undefined,
        video_url:   videoUrl  || undefined,
        categories:  categories.split(',').map(s => s.trim()).filter(Boolean),
        nutrition:   nutritionPayload as any,
        ingredients: parsedIngredients,
        steps:       parsedSteps,
        food_group:    foodGroup    || null,
        protein_type:  proteinType  || null,
        grain_type:    grainType    || null,
        suitable_for:  suitableFor,
        is_fatty_fish: isFattyFish,
        is_red_meat:   isRedMeat,
      };

      const { data } = await recipesApi.update(recipe.id, payload);
      onSaved(data);
      onClose();
    } catch (e) {
      setError(getErrorMessage(e) || String(e));
    } finally {
      setSaving(false);
    }
  };

  const tabs = [
    { id: 'basic',          label: 'Основное' },
    { id: 'nutrition',      label: 'КБЖУ' },
    { id: 'classification', label: 'Классификация' },
    { id: 'ingredients',    label: 'Ингредиенты' },
    { id: 'steps',          label: 'Шаги' },
  ] as const;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>

        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-bold text-chocolate">Редактировать блюдо</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
        </div>

        <div className="flex border-b px-6 overflow-x-auto">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition whitespace-nowrap ${tab === t.id ? 'border-tomato text-tomato' : 'border-transparent text-gray-500 hover:text-chocolate'}`}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {tab === 'basic' && (
            <>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Название *</label>
                <Input value={title} onChange={e => setTitle(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Время готовки</label>
                  <Input value={cookTime} onChange={e => setCookTime(e.target.value)} placeholder="напр. 30 мин" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Порций</label>
                  <Input type="number" value={servings} onChange={e => setServings(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Кухня</label>
                <Input value={country} onChange={e => setCountry(e.target.value)} placeholder="Русская / Итальянская / ..." />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Категории (через запятую)</label>
                <Input value={categories} onChange={e => setCategories(e.target.value)} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Изображение (URL)</label>
                <div className="flex gap-2">
                  <Input value={imageUrl} onChange={e => setImageUrl(e.target.value)} className="flex-1" />
                  <button type="button" onClick={() => imgInputRef.current?.click()} disabled={uploadingImg}
                    className="px-3 py-2 text-sm rounded-xl bg-gray-100 hover:bg-gray-200 disabled:opacity-50">
                    {uploadingImg ? 'Загрузка...' : 'Файл'}
                  </button>
                  <input ref={imgInputRef} type="file" accept="image/*" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f, 'image'); e.target.value = ''; }} />
                </div>
                <p className="text-xs text-gray-400 mt-1">JPEG/PNG/WebP/GIF — до 10 МБ</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Видео (URL)</label>
                <div className="flex gap-2">
                  <Input value={videoUrl} onChange={e => setVideoUrl(e.target.value)} className="flex-1" />
                  <button type="button" onClick={() => vidInputRef.current?.click()} disabled={uploadingVid}
                    className="px-3 py-2 text-sm rounded-xl bg-gray-100 hover:bg-gray-200 disabled:opacity-50">
                    {uploadingVid ? 'Загрузка...' : 'Файл'}
                  </button>
                  <input ref={vidInputRef} type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f, 'video'); e.target.value = ''; }} />
                </div>
                <p className="text-xs text-gray-400 mt-1">MP4, WebM, MOV — до 200 МБ</p>
              </div>
            </>
          )}

          {tab === 'nutrition' && (
            <div className="grid grid-cols-2 gap-4">
              {NUTRITION_LABELS.map(({ key, label, unit }) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 mb-1 block">{label} ({unit})</label>
                  <Input type="number" step="0.1" value={nutrition[key]}
                    onChange={e => setNutrition(prev => ({ ...prev, [key]: e.target.value }))} />
                </div>
              ))}
            </div>
          )}

          {tab === 'classification' && (
            <div className="space-y-5">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Группа продукта (метод тарелки)</label>
                <select value={foodGroup} onChange={e => setFoodGroup(e.target.value as FoodGroup | '')}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-tomato/40">
                  <option value="">— не указано —</option>
                  {FOOD_GROUP_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {foodGroup === 'protein' && (
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Тип белка *</label>
                  <select value={proteinType} onChange={e => setProteinType(e.target.value as ProteinType | '')}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-tomato/40">
                    <option value="">— не указано —</option>
                    {PROTEIN_TYPE_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {foodGroup === 'grain' && (
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Тип зерна *</label>
                  <select value={grainType} onChange={e => setGrainType(e.target.value as GrainType | '')}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-tomato/40">
                    <option value="">— не указано —</option>
                    {GRAIN_TYPE_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="text-xs text-gray-500 mb-2 block">Подходит для приёмов пищи</label>
                <div className="grid grid-cols-2 gap-2">
                  {SUITABLE_FOR_OPTIONS.map(o => (
                    <label key={o.value} className="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-50">
                      <input type="checkbox" checked={suitableFor.includes(o.value)}
                        onChange={() => toggleSuitable(o.value)} />
                      <span className="text-sm">{o.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-50">
                  <input type="checkbox" checked={isFattyFish} onChange={e => setIsFattyFish(e.target.checked)} />
                  <span className="text-sm">Жирная рыба (лосось, скумбрия, сельдь, форель)</span>
                </label>
                <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-50">
                  <input type="checkbox" checked={isRedMeat} onChange={e => setIsRedMeat(e.target.checked)} />
                  <span className="text-sm">Красное мясо (говядина, баранина, свинина, утка)</span>
                </label>
              </div>
            </div>
          )}

          {tab === 'ingredients' && (
            <div>
              <label className="text-xs text-gray-500 mb-1 block">JSON массив ингредиентов</label>
              <textarea className="w-full h-64 text-xs font-mono border rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-tomato/40"
                value={ingredients} onChange={e => setIngredients(e.target.value)} spellCheck={false} />
              <p className="text-xs text-gray-400 mt-1">{'[{"name": "...", "quantity": "...", "unit": "..."}, ...]'}</p>
            </div>
          )}

          {tab === 'steps' && (
            <div>
              <label className="text-xs text-gray-500 mb-1 block">JSON массив шагов</label>
              <textarea className="w-full h-64 text-xs font-mono border rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-tomato/40"
                value={steps} onChange={e => setSteps(e.target.value)} spellCheck={false} />
              <p className="text-xs text-gray-400 mt-1">{'[{"text": "...", "photo": null}, ...]'}</p>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t flex items-center justify-between gap-3">
          {error && <p className="text-sm text-red-600 flex-1">{error}</p>}
          <div className="flex gap-3 ml-auto">
            <Button variant="ghost" onClick={onClose} disabled={saving}>Отмена</Button>
            <Button onClick={handleSave} disabled={saving || !title.trim()}>
              {saving ? 'Сохранение...' : 'Сохранить'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
