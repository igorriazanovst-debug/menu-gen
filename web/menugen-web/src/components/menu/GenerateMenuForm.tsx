// MG_607_V_web: компактная форма генерации меню.
//
// UI:
//  - КБЖУ-summary вверху (read-only)
//  - Период + Приёмов пищи (3/5)
//  - Страны: чипы топ-6 популярных + кнопка «Больше» (раскрывает все)
//  - Макс. время готовки (input minutes)
//  - Аллергены toggle ON/OFF (из profile)
//  - Нелюбимые toggle ON/OFF (из profile)
import React, { useEffect, useMemo, useState } from 'react';
import { menuApi, type GenerateMenuPayload } from '../../api/menu';
import { recipesApi } from '../../api/recipes';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import type { Menu, MealPlan, UserProfile } from '../../types';

// Маппинг кодов стран → display names. Если кода нет в маппинге — показываем как есть.
const COUNTRY_LABELS: Record<string, string> = {
  RU: '🇷🇺 Россия',
  IT: '🇮🇹 Италия',
  FR: '🇫🇷 Франция',
  US: '🇺🇸 США',
  JP: '🇯🇵 Япония',
  CN: '🇨🇳 Китай',
  MX: '🇲🇽 Мексика',
  IN: '🇮🇳 Индия',
  GR: '🇬🇷 Греция',
  ES: '🇪🇸 Испания',
  TR: '🇹🇷 Турция',
  TH: '🇹🇭 Таиланд',
  Россия: '🇷🇺 Россия',
  Италия: '🇮🇹 Италия',
  Франция: '🇫🇷 Франция',
};

const POPULAR_COUNTRIES_LIMIT = 6;

function todayISO() {
  return new Date().toISOString().split('T')[0];
}

interface Props {
  onCreated: (menu: Menu) => void;
  onCancel: () => void;
  userAllergies: string[];
  userDisliked: string[];
  userProfile?: UserProfile;
  initialMealPlan: MealPlan;
}

export const GenerateMenuForm: React.FC<Props> = ({
  onCreated,
  onCancel,
  userAllergies,
  userDisliked,
  userProfile,
  initialMealPlan,
}) => {
  const [periodDays, setPeriodDays] = useState(7);
  const [startDate, setStartDate] = useState(todayISO());
  const [mealPlanType, setMealPlanType] = useState<MealPlan>(initialMealPlan);

  // страны
  const [allCountries, setAllCountries] = useState<string[]>([]);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [showAllCountries, setShowAllCountries] = useState(false);

  // прочие фильтры
  const [maxCookTime, setMaxCookTime] = useState<number | ''>('');
  const [respectAllergies, setRespectAllergies] = useState(true);
  const [respectDisliked, setRespectDisliked] = useState(true);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    recipesApi.countries()
      .then(r => {
        const data = r.data;
        // backend отдаёт либо ['RU','IT'] либо {countries: [...]}, защитимся
        const list: string[] = Array.isArray(data)
          ? data
          : ((data as any)?.countries ?? []);
        setAllCountries(list);
      })
      .catch(() => setAllCountries([]));
  }, []);

  const popularCountries = useMemo(
    () => allCountries.slice(0, POPULAR_COUNTRIES_LIMIT),
    [allCountries],
  );
  const restCountries = useMemo(
    () => allCountries.slice(POPULAR_COUNTRIES_LIMIT),
    [allCountries],
  );

  const toggleCountry = (c: string) => {
    setSelectedCountries(prev =>
      prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c],
    );
  };

  // КБЖУ из profile (если есть)
  const targets = userProfile && userProfile.calorie_target ? {
    cal: userProfile.calorie_target,
    p: userProfile.protein_target_g,
    f: userProfile.fat_target_g,
    c: userProfile.carb_target_g,
  } : null;

  const handleSubmit = async () => {
    setGenerating(true); setError('');
    try {
      const payload: GenerateMenuPayload = {
        period_days: periodDays,
        start_date: startDate,
        meal_plan_type: mealPlanType,
      };
      if (selectedCountries.length > 0) payload.countries = selectedCountries;
      if (maxCookTime !== '' && Number(maxCookTime) > 0) payload.max_cook_time = Number(maxCookTime);
      if (!respectAllergies) payload.exclude_allergens = [];
      if (!respectDisliked) payload.exclude_disliked = [];

      const { data } = await menuApi.generate(payload);
      onCreated(data);
    } catch (e: any) {
      const msg = e?.response?.data?.message
        || e?.response?.data?.detail
        || 'Ошибка генерации меню';
      setError(msg);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card className="p-5 space-y-5">
      {/* КБЖУ-summary */}
      {targets ? (
        <div className="rounded-xl bg-rice/50 px-3 py-2 text-xs text-chocolate">
          <span className="font-semibold">Цели из Профиля:</span>{' '}
          <span>{targets.cal} ккал</span>
          {(targets.p || targets.f || targets.c) && (
            <span className="text-gray-600">
              {' '}/ Б {targets.p ?? '—'} · Ж {targets.f ?? '—'} · У {targets.c ?? '—'} г
            </span>
          )}
        </div>
      ) : (
        <div className="rounded-xl bg-yellow-50 px-3 py-2 text-xs text-yellow-700">
          Цели КБЖУ не заданы. Заполни Профиль для персонализации.
        </div>
      )}

      {/* Период + Приёмов пищи в одной строке */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">С даты</label>
          <input
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-tomato"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Период (дней)</label>
          <input
            type="number" min={1} max={30}
            value={periodDays}
            onChange={e => setPeriodDays(Number(e.target.value) || 1)}
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-tomato"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Приёмов пищи</label>
          <div className="flex gap-1">
            {(['3', '5'] as const).map(v => (
              <button
                key={v}
                type="button"
                onClick={() => setMealPlanType(v)}
                className={[
                  'flex-1 px-3 py-2 rounded-xl border text-sm transition',
                  mealPlanType === v
                    ? 'border-tomato bg-tomato/10 text-tomato'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-tomato/50',
                ].join(' ')}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Страны кухни */}
      {allCountries.length > 0 && (
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            Кухня {selectedCountries.length > 0 && (
              <span className="text-tomato">({selectedCountries.length} выбрано)</span>
            )}
            {selectedCountries.length === 0 && <span className="text-gray-400"> — все</span>}
          </label>
          <div className="flex flex-wrap gap-2">
            {popularCountries.map(c => {
              const active = selectedCountries.includes(c);
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleCountry(c)}
                  className={[
                    'px-3 py-1.5 rounded-full border text-xs transition',
                    active
                      ? 'border-tomato bg-tomato text-white'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-tomato/50',
                  ].join(' ')}
                >
                  {COUNTRY_LABELS[c] ?? c}
                </button>
              );
            })}
            {restCountries.length > 0 && (
              <button
                type="button"
                onClick={() => setShowAllCountries(s => !s)}
                className="px-3 py-1.5 rounded-full border border-dashed border-gray-300 text-xs text-gray-500 hover:border-tomato/50"
              >
                {showAllCountries ? 'Свернуть' : `Больше (+${restCountries.length})`}
              </button>
            )}
          </div>
          {showAllCountries && restCountries.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-gray-100">
              {restCountries.map(c => {
                const active = selectedCountries.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleCountry(c)}
                    className={[
                      'px-3 py-1.5 rounded-full border text-xs transition',
                      active
                        ? 'border-tomato bg-tomato text-white'
                        : 'border-gray-200 bg-white text-gray-600 hover:border-tomato/50',
                    ].join(' ')}
                  >
                    {COUNTRY_LABELS[c] ?? c}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Время готовки */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Макс. время готовки (мин){' '}
          <span className="text-gray-400">— опционально</span>
        </label>
        <input
          type="number" min={5} step={5}
          value={maxCookTime}
          onChange={e => setMaxCookTime(e.target.value ? Number(e.target.value) : '')}
          placeholder="Не ограничено"
          className="w-40 px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-tomato"
        />
      </div>

      {/* Аллергены + Нелюбимые — ON/OFF toggles */}
      <div className="space-y-2">
        <ToggleRow
          checked={respectAllergies}
          onChange={setRespectAllergies}
          title="Учитывать аллергены из Профиля"
          subtitle={userAllergies.length > 0 ? userAllergies.join(', ') : 'Список пуст'}
          disabled={userAllergies.length === 0}
        />
        <ToggleRow
          checked={respectDisliked}
          onChange={setRespectDisliked}
          title="Учитывать нелюбимые продукты"
          subtitle={userDisliked.length > 0 ? userDisliked.join(', ') : 'Список пуст'}
          disabled={userDisliked.length === 0}
        />
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
        <Button variant="ghost" onClick={onCancel} disabled={generating}>Отмена</Button>
        <Button onClick={handleSubmit} loading={generating}>Создать меню</Button>
      </div>
    </Card>
  );
};


interface ToggleRowProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  title: string;
  subtitle: string;
  disabled?: boolean;
}

const ToggleRow: React.FC<ToggleRowProps> = ({ checked, onChange, title, subtitle, disabled }) => {
  return (
    <div className={[
      'flex items-center gap-3 p-3 rounded-xl border transition',
      disabled
        ? 'border-gray-100 bg-gray-50 opacity-60'
        : 'border-gray-200 bg-white hover:border-tomato/30',
    ].join(' ')}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={[
          'relative w-10 h-6 rounded-full transition flex-shrink-0',
          checked && !disabled ? 'bg-tomato' : 'bg-gray-300',
          disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        ].join(' ')}
      >
        <span
          className={[
            'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          ].join(' ')}
        />
      </button>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-chocolate font-medium">{title}</p>
        <p className="text-xs text-gray-500 truncate">{subtitle}</p>
      </div>
    </div>
  );
};
