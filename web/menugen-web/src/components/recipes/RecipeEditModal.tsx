import React, { useRef, useState } from 'react';
import { recipesApi } from '../../api/recipes';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { getErrorMessage } from '../../utils/api';
import type { Recipe } from '../../types';

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
  const [saving,       setSaving]       = useState(false);
  const [uploadingImg, setUploadingImg] = useState(false);
  const [uploadingVid, setUploadingVid] = useState(false);
  const [error,        setError]        = useState('');
  const [tab,          setTab]          = useState<'basic' | 'nutrition' | 'ingredients' | 'steps'>('basic');

  const imgInputRef = useRef<HTMLInputElement>(null);
  const vidInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File, type: 'image' | 'video') => {
    const setUploading = type === 'image' ? setUploadingImg : setUploadingVid;
    setUploading(true);
    setError('');
    try {
      const { data } = await recipesApi.uploadMedia(file, type);
      if (type === 'image') setImageUrl(data.url);
      else setVideoUrl(data.url);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      let parsedIngredients = recipe.ingredients;
      let parsedSteps = recipe.steps;
      try { parsedIngredients = JSON.parse(ingredients); } catch { throw new Error('Ошибка JSON в ингредиентах'); }
      try { parsedSteps = JSON.parse(steps); } catch { throw new Error('Ошибка JSON в шагах'); }

      const nutritionPayload: Record<string, { value: string; unit: string }> = {};
      NUTRITION_LABELS.forEach(({ key, unit }) => {
        if (nutrition[key]) nutritionPayload[key] = { value: nutrition[key], unit };
      });

      const payload: Partial<Recipe> = {
        title,
        cook_time:   cookTime  || undefined,
        servings:    servings  ? Number(servings) : undefined,
        country:     country   || undefined,
        image_url:   imageUrl  || undefined,
        video_url:   videoUrl  || undefined,
        categories:  categories.split(',').map(s => s.trim()).filter(Boolean),
        nutrition:   nutritionPayload as any,
        ingredients: parsedIngredients,
        steps:       parsedSteps,
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
    { id: 'basic',       label: 'Основное' },
    { id: 'nutrition',   label: 'КБЖУ' },
    { id: 'ingredients', label: 'Ингредиенты' },
    { id: 'steps',       label: 'Шаги' },
  ] as const;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>

        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-bold text-chocolate">Редактировать блюдо</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
        </div>

        <div className="flex border-b px-6">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition ${tab === t.id ? 'border-tomato text-tomato' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {tab === 'basic' && (
            <>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Изображение</label>
                {imageUrl && (
                  <div className="relative mb-2">
                    <img src={imageUrl} alt="" className="w-full h-44 object-cover rounded-xl"
                      onError={e => { e.currentTarget.style.display = 'none'; }} />
                    <button onClick={() => setImageUrl('')}
                      className="absolute top-2 right-2 bg-white/90 rounded-full w-6 h-6 flex items-center justify-center text-gray-500 hover:text-red-500 shadow text-sm">x</button>
                  </div>
                )}
                <div className="flex gap-2">
                  <Input className="flex-1" value={imageUrl} onChange={e => setImageUrl(e.target.value)} placeholder="https://... или загрузите файл" />
                  <button type="button" onClick={() => imgInputRef.current?.click()} disabled={uploadingImg}
                    className="shrink-0 px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition disabled:opacity-50">
                    {uploadingImg ? 'Загрузка...' : 'Файл'}
                  </button>
                  <input ref={imgInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f, 'image'); e.target.value = ''; }} />
                </div>
                <p className="text-xs text-gray-400 mt-1">JPEG, PNG, WebP, GIF — до 10 МБ</p>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Название *</label>
                <Input value={title} onChange={e => setTitle(e.target.value)} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Время приготовления</label>
                  <Input value={cookTime} onChange={e => setCookTime(e.target.value)} placeholder="30 мин" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Порций</label>
                  <Input type="number" value={servings} onChange={e => setServings(e.target.value)} />
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Страна / Кухня</label>
                <Input value={country} onChange={e => setCountry(e.target.value)} placeholder="RU" />
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Категории (через запятую)</label>
                <Input value={categories} onChange={e => setCategories(e.target.value)} placeholder="Завтрак, Русская" />
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Видео</label>
                {videoUrl && (
                  <div className="relative mb-2">
                    <video src={videoUrl} controls className="w-full rounded-xl max-h-40" />
                    <button onClick={() => setVideoUrl('')}
                      className="absolute top-2 right-2 bg-white/90 rounded-full w-6 h-6 flex items-center justify-center text-gray-500 hover:text-red-500 shadow text-sm">x</button>
                  </div>
                )}
                <div className="flex gap-2">
                  <Input className="flex-1" value={videoUrl} onChange={e => setVideoUrl(e.target.value)} placeholder="https://... или загрузите файл" />
                  <button type="button" onClick={() => vidInputRef.current?.click()} disabled={uploadingVid}
                    className="shrink-0 px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition disabled:opacity-50">
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
