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
import { familyApi } from '../../api/family';
import { recipesApi } from '../../api/recipes';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import type { Menu, MealPlan, UserProfile, MenuQuota } from '../../types';
import { allergenLabel } from '../../constants/allergens';

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
  menuQuota?: MenuQuota | null; // Freemium: остаток бесплатных генераций
}

export const GenerateMenuForm: React.FC<Props> = ({
  onCreated,
  onCancel,
  userAllergies,
  userDisliked,
  userProfile,
  initialMealPlan,
  menuQuota,
}) => {
  const [periodDays, setPeriodDays] = useState(7);
  const [startDate, setStartDate] = useState(todayISO());
  const [mealPlanType, setMealPlanType] = useState<MealPlan>(initialMealPlan);
  const [strategy, setStrategy] = useState<'1' | '2' | '3'>('1'); // MG_STRAT_WEB

  // страны
  const [allCountries, setAllCountries] = useState<string[]>([]);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [showAllCountries, setShowAllCountries] = useState(false);

  // прочие фильтры
  const [maxCookTime, setMaxCookTime] = useState<number | ''>('');
  const [respectAllergies, setRespectAllergies] = useState(true);
  const [respectDisliked, setRespectDisliked] = useState(true);
  const [withSoup, setWithSoup] = useState(true); // MG_610_V_web

  // MG_FAMILYGEN: члены семьи + режим (family | per_member).
  const [members, setMembers] = useState<{ id: number; name: string }[]>([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState<number[]>([]);
  const [menuMode, setMenuMode] = useState<'family' | 'per_member'>('family');

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    familyApi.get()
      .then(r => {
        const ms = ((r.data?.members ?? []) as any[]).map(m => ({
          id: m.id, name: (m.name as string) || 'Участник',
        }));
        setMembers(ms);
        setSelectedMemberIds(ms.map(m => m.id));
      })
      .catch(() => setMembers([]));
  }, []);

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

  const toggleMember = (id: number) => {
    setSelectedMemberIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    );
  };
  const multiMember = members.length > 1;
  const noMemberSelected = multiMember && selectedMemberIds.length === 0;

  // КБЖУ из profile (если есть)
  const targets = userProfile && userProfile.calorie_target ? {
    cal: userProfile.calorie_target,
    p: userProfile.protein_target_g,
    f: userProfile.fat_target_g,
    c: userProfile.carb_target_g,
  } : null;

  // Freemium: остаток бесплатных генераций (limit=null → безлимит/premium).
  const hasLimit = !!menuQuota && menuQuota.limit !== null && menuQuota.limit !== undefined;
  const remaining = hasLimit ? Math.max(0, (menuQuota!.limit as number) - menuQuota!.used) : null;
  const quotaExhausted = hasLimit && remaining === 0;
  const resetLabel = menuQuota?.reset_at
    ? new Date(menuQuota.reset_at).toLocaleDateString('ru')
    : '';

  const handleSubmit = async () => {
    setGenerating(true); setError('');
    try {
      const payload: GenerateMenuPayload = {
        period_days: periodDays,
        start_date: startDate,
        strategy, // MG_STRAT_WEB
      };
      // MG_MEALCOUNT: число приёмов теперь соблюдают и «Стандарт», и «По составу»
      // (раньше вторая всегда добирала два перекуса, сколько приёмов ни выбери).
      if (strategy !== '3') payload.meal_plan_type = mealPlanType;
      if (selectedCountries.length > 0) payload.countries = selectedCountries;
      if (maxCookTime !== '' && Number(maxCookTime) > 0) payload.max_cook_time = Number(maxCookTime);
      if (!respectAllergies) payload.exclude_allergens = [];
      if (!respectDisliked) payload.exclude_disliked = [];
      payload.with_soup = withSoup; // MG_610_V_web
      // MG_FAMILYGEN: члены семьи + режим. Для одного члена не шлём — бэкенд
      // по умолчанию генерит на всю семью (= этот единственный член).
      if (multiMember && selectedMemberIds.length > 0) {
        payload.member_ids = selectedMemberIds;
        payload.mode = selectedMemberIds.length > 1 ? menuMode : 'family';
      }

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
      {/* Freemium: остаток бесплатных генераций */}
      {hasLimit && (
        <div className={[
          'rounded-xl px-3 py-2 text-xs flex items-center justify-between gap-2',
          quotaExhausted ? 'bg-red-50 text-red-700' : 'bg-rice/60 text-chocolate',
        ].join(' ')}>
          <span>
            <span className="font-semibold">Бесплатные генерации:</span>{' '}
            осталось {remaining} из {menuQuota!.limit}
            {resetLabel && <span className="text-gray-500"> · сброс {resetLabel}</span>}
          </span>
          {quotaExhausted && <span className="font-semibold whitespace-nowrap">Лимит исчерпан</span>}
        </div>
      )}

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
      {/* MG_STRAT_WEB strategy selector */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Стратегия меню</label>
        <div className="flex flex-col gap-1">
          {([
            ['1', 'Стандарт', 'Метод тарелки по ролям; выбор 3 или 5 приёмов'],
            ['2', 'По составу', 'Каждый приём по макро-ролям (белок/жир/углевод/клетчатка)'],
            ['3', 'Тарелка 25/25/50', 'Белок/гарнир/овощи в пропорции по массе'],
          ] as const).map(([v, title, desc]) => (
            <button
              key={v}
              type="button"
              onClick={() => setStrategy(v)}
              className={[
                'text-left px-3 py-2 rounded-xl border text-sm transition',
                strategy === v
                  ? 'border-tomato bg-tomato/10 text-tomato'
                  : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
              ].join(' ')}
            >
              <span className="font-medium">{title}</span>
              <span className="block text-xs text-gray-400">{desc}</span>
            </button>
          ))}
        </div>
      </div>

      <div className={`grid grid-cols-1 gap-3 ${strategy === '1' ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
        <div>
          <label className="block text-xs text-gray-500 mb-1">С даты</label>
          <input
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className="w-full px-3 py-2 rounded-xl border border-border focus:outline-none focus:border-tomato"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Период (дней)</label>
          <input
            type="number" min={1} max={30}
            value={periodDays}
            onChange={e => setPeriodDays(Number(e.target.value) || 1)}
            className="w-full px-3 py-2 rounded-xl border border-border focus:outline-none focus:border-tomato"
          />
        </div>
        {strategy !== '3' && (  /* MG_MEALCOUNT: в «тарелке 25/25/50» перекусов нет */
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
                    : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
                ].join(' ')}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
        )}
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
                      : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
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
            <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-border">
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
                        : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
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
          className="w-40 px-3 py-2 rounded-xl border border-border focus:outline-none focus:border-tomato"
        />
      </div>

      {/* MG_FAMILYGEN: для кого меню (только если в семье >1 члена) */}
      {multiMember && (
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            Для кого меню{' '}
            <span className="text-tomato">({selectedMemberIds.length} из {members.length})</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {members.map(m => {
              const active = selectedMemberIds.includes(m.id);
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggleMember(m.id)}
                  className={[
                    'px-3 py-1.5 rounded-full border text-xs transition',
                    active
                      ? 'border-tomato bg-tomato text-white'
                      : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
                  ].join(' ')}
                >
                  {m.name}
                </button>
              );
            })}
          </div>
          {selectedMemberIds.length > 1 && (
            <div className="mt-2 flex gap-1">
              {([
                ['family', 'Общее меню', 'Одно меню на всех выбранных'],
                ['per_member', 'Каждому своё', 'Отдельные блюда под каждого'],
              ] as const).map(([v, title, desc]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setMenuMode(v)}
                  className={[
                    'flex-1 text-left px-3 py-2 rounded-xl border text-sm transition',
                    menuMode === v
                      ? 'border-tomato bg-tomato/10 text-tomato'
                      : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
                  ].join(' ')}
                >
                  <span className="font-medium">{title}</span>
                  <span className="block text-xs text-gray-400">{desc}</span>
                </button>
              ))}
            </div>
          )}
          {noMemberSelected && (
            <p className="text-xs text-red-600 mt-1">Выберите хотя бы одного члена семьи.</p>
          )}
        </div>
      )}

      {/* Аллергены + Нелюбимые — ON/OFF toggles */}
      <div className="space-y-2">
        <ToggleRow
          checked={respectAllergies}
          onChange={setRespectAllergies}
          title="Учитывать аллергены из Профиля"
          subtitle={userAllergies.length > 0 ? userAllergies.map(allergenLabel).join(', ') : 'Список пуст'}
          disabled={userAllergies.length === 0}
        />
        <ToggleRow
          checked={respectDisliked}
          onChange={setRespectDisliked}
          title="Учитывать нелюбимые продукты"
          subtitle={userDisliked.length > 0 ? userDisliked.join(', ') : 'Список пуст'}
          disabled={userDisliked.length === 0}
        />
        {/* MG_610_V_web: with_soup toggle */}
        <ToggleRow
          checked={withSoup}
          onChange={setWithSoup}
          title="Суп на обед"
          subtitle={withSoup ? 'Первое блюдо включено в обед' : 'Обед без супа'}
        />
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {quotaExhausted && !error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          Лимит бесплатных генераций исчерпан. Оформите Premium для безлимитной
          генерации{resetLabel && ` или дождитесь сброса ${resetLabel}`}.
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-border">
        <Button variant="ghost" onClick={onCancel} disabled={generating}>Отмена</Button>
        <Button onClick={handleSubmit} loading={generating} disabled={quotaExhausted || noMemberSelected}>Создать меню</Button>
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
        ? 'border-border bg-gray-50 opacity-60'
        : 'border-border bg-surface hover:border-tomato/30',
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
            'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-surface shadow transition-transform',
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
