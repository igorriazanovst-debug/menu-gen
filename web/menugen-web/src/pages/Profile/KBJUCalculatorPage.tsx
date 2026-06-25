// MG_206_V_calc_page = 1
import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { setUser } from '../../store/slices/authSlice';
import { usersApi } from '../../api/users';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { getErrorMessage } from '../../utils/api';
import type {
  KBJURequest,
  KBJUResult,
  KBJUSystem,
  KBJUDiet,
  KBJUCustomMode,
} from '../../types';

// ─── Static config (отзеркаливает backend SYSTEMS/DIET_PRESETS) ──────────────
const SYSTEMS: { value: KBJUSystem; label: string; hint: string }[] = [
  { value: 'mifflin',         label: 'Mifflin-St Jeor',       hint: 'Универсальная (США/мир)' },
  { value: 'harris_benedict', label: 'Harris-Benedict',       hint: 'Revised, США' },
  { value: 'rospotrebnadzor', label: 'Роспотребнадзор (RU)',  hint: 'МР 2.3.1.0253-21' },
  { value: 'efsa',            label: 'EFSA (EU)',             hint: 'Европейский подход' },
  { value: 'custom',          label: 'Свои значения',         hint: 'Ввести вручную' },
];

const DIETS: { value: KBJUDiet; label: string; pct: string }[] = [
  { value: 'balanced',     label: 'Сбалансированный',  pct: 'Б 20 / Ж 30 / У 50' },
  { value: 'high_protein', label: 'Высокобелковый',    pct: 'Б 35 / Ж 25 / У 40' },
  { value: 'low_carb',     label: 'Низкоуглеводный',   pct: 'Б 30 / Ж 45 / У 25' },
];

const GENDERS = [
  { value: 'male',   label: 'Мужской' },
  { value: 'female', label: 'Женский' },
  { value: 'other',  label: 'Иной' },
];

const ACTIVITIES = [
  { value: 'sedentary',   label: 'Сидячий (×1.2)' },
  { value: 'light',       label: 'Лёгкая (×1.375)' },
  { value: 'moderate',    label: 'Умеренная (×1.55)' },
  { value: 'active',      label: 'Высокая (×1.725)' },
  { value: 'very_active', label: 'Очень высокая (×1.9)' },
];

const GOALS = [
  { value: 'lose_weight', label: 'Похудение (−500 ккал)' },
  { value: 'maintain',    label: 'Поддержание' },
  { value: 'gain_weight', label: 'Набор массы (+300 ккал)' },
];

// ─── Component ──────────────────────────────────────────────────────────────
export const KBJUCalculatorPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const profile = user?.profile;

  // Step 1: system
  const [system, setSystem] = useState<KBJUSystem>('mifflin');
  // Step 2: diet (only for non-custom)
  const [diet, setDiet] = useState<KBJUDiet>('balanced');
  // Step 3a: base inputs (prefill from profile)
  const [heightCm,  setHeightCm]   = useState<string>(profile?.height_cm ? String(profile.height_cm) : '');
  const [weightKg,  setWeightKg]   = useState<string>(profile?.weight_kg ? String(profile.weight_kg) : '');
  const [birthYear, setBirthYear]  = useState<string>(profile?.birth_year ? String(profile.birth_year) : '');
  const [gender,    setGender]     = useState<string>(profile?.gender || 'male');
  const [activity,  setActivity]   = useState<string>(profile?.activity_level || 'moderate');
  const [goal,      setGoal]       = useState<string>(profile?.goal || 'maintain');

  // Step 3b: custom mode
  const [customMode, setCustomMode] = useState<KBJUCustomMode>('percents');
  const [customCal, setCustomCal]   = useState<string>('2000');
  const [customP,   setCustomP]     = useState<string>('120');
  const [customF,   setCustomF]     = useState<string>('65');
  const [customC,   setCustomC]     = useState<string>('250');
  const [customFib, setCustomFib]   = useState<string>('28');
  const [customDelta, setCustomDelta] = useState<string>('0');
  const [customPP, setCustomPP]     = useState<string>('20');
  const [customFP, setCustomFP]     = useState<string>('30');
  const [customCP, setCustomCP]     = useState<string>('50');

  // Result + UI state
  const [result, setResult] = useState<KBJUResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  useEffect(() => {
    setResult(null);
    setError('');
    setSuccess('');
  }, [system, diet, customMode]);

  const buildRequest = (): KBJURequest => {
    if (system !== 'custom') {
      return {
        system,
        diet,
        height_cm: heightCm ? Number(heightCm) : undefined,
        weight_kg: weightKg || undefined,
        birth_year: birthYear ? Number(birthYear) : undefined,
        gender: gender as KBJURequest['gender'],
        activity_level: activity as KBJURequest['activity_level'],
        goal: goal as KBJURequest['goal'],
      };
    }
    if (customMode === 'grams') {
      return {
        system: 'custom',
        custom_mode: 'grams',
        custom_calorie_target: Number(customCal),
        custom_protein_g: customP,
        custom_fat_g: customF,
        custom_carb_g: customC,
        custom_fiber_g: customFib,
      };
    }
    return {
      system: 'custom',
      custom_mode: 'percents',
      height_cm: heightCm ? Number(heightCm) : undefined,
      weight_kg: weightKg || undefined,
      birth_year: birthYear ? Number(birthYear) : undefined,
      gender: gender as KBJURequest['gender'],
      activity_level: activity as KBJURequest['activity_level'],
      custom_calorie_delta: Number(customDelta),
      custom_protein_pct: Number(customPP),
      custom_fat_pct: Number(customFP),
      custom_carb_pct: Number(customCP),
      custom_fiber_g: customFib,
    };
  };

  const onCalc = async () => {
    setLoading(true); setError(''); setSuccess(''); setResult(null);
    try {
      const { data } = await usersApi.calcPreview(buildRequest());
      setResult(data);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const onApply = async () => {
    setApplying(true); setError(''); setSuccess('');
    try {
      const { data } = await usersApi.calcApply(buildRequest());
      dispatch(setUser(data));
      setSuccess('Целевые КБЖУ сохранены в профиль!');
      setTimeout(() => navigate('/profile'), 800);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setApplying(false);
    }
  };

  const pctSum = useMemo(
    () => Number(customPP || 0) + Number(customFP || 0) + Number(customCP || 0),
    [customPP, customFP, customCP],
  );

  // ─── render ────────────────────────────────────────────────────────────────
  const isCustom = system === 'custom';
  const isCustomGrams = isCustom && customMode === 'grams';
  const isCustomPercents = isCustom && customMode === 'percents';
  const needsBaseInputs = !isCustomGrams; // preset + custom/percents требуют base inputs

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/profile')}>← Профиль</Button>
        <h1 className="text-2xl font-bold text-chocolate">Калькулятор КБЖУ</h1>
      </div>

      {/* Disclaimer */}
      <Card className="p-4 bg-yellow-50 border-yellow-200">
        <div className="text-sm text-yellow-900 leading-relaxed">
          <p className="font-semibold mb-1">⚠️ Важно</p>
          <p>
            Все расчёты носят <b>справочный характер</b> и не заменяют консультацию врача.
            При наличии заболеваний (диабет, сердечно-сосудистые, ЖКТ, почек и др.) перед изменением
            рациона обязательно проконсультируйтесь со специалистом. Формулы дают только стартовую
            оценку — реальные потребности зависят от индивидуальных особенностей, образа жизни и здоровья.
          </p>
        </div>
      </Card>

      {/* Step 1: System */}
      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-3">1. Система расчёта</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {SYSTEMS.map((s) => {
            const active = system === s.value;
            return (
              <button
                type="button"
                key={s.value}
                onClick={() => setSystem(s.value)}
                className={
                  'p-3 rounded-xl border text-left transition ' +
                  (active
                    ? 'border-tomato bg-tomato/10 text-chocolate'
                    : 'border-border bg-surface hover:border-tomato/50 text-gray-700')
                }
              >
                <div className="font-semibold">{s.label}</div>
                <div className="text-xs opacity-70">{s.hint}</div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Step 2: Diet (only for non-custom) */}
      {!isCustom && (
        <Card className="p-6">
          <h2 className="text-lg font-bold text-chocolate mb-3">2. Пресет диеты</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {DIETS.map((d) => {
              const active = diet === d.value;
              return (
                <button
                  type="button"
                  key={d.value}
                  onClick={() => setDiet(d.value)}
                  className={
                    'p-3 rounded-xl border text-left transition ' +
                    (active
                      ? 'border-tomato bg-tomato/10 text-chocolate'
                      : 'border-border bg-surface hover:border-tomato/50 text-gray-700')
                  }
                >
                  <div className="font-semibold">{d.label}</div>
                  <div className="text-xs opacity-70">{d.pct}</div>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {/* Step 2b: Custom mode (only for custom) */}
      {isCustom && (
        <Card className="p-6">
          <h2 className="text-lg font-bold text-chocolate mb-3">2. Режим ввода</h2>
          <div className="grid grid-cols-2 gap-2">
            {(['percents', 'grams'] as KBJUCustomMode[]).map((m) => {
              const active = customMode === m;
              const label = m === 'percents' ? '% БЖУ + дельта от TDEE' : 'Граммы Б/Ж/У + ккал';
              return (
                <button
                  type="button"
                  key={m}
                  onClick={() => setCustomMode(m)}
                  className={
                    'p-3 rounded-xl border text-left transition ' +
                    (active
                      ? 'border-tomato bg-tomato/10 text-chocolate'
                      : 'border-border bg-surface hover:border-tomato/50 text-gray-700')
                  }
                >
                  <div className="font-semibold">{label}</div>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {/* Step 3: Inputs */}
      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-3">3. Исходные данные</h2>

        {needsBaseInputs && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Рост, см" type="number" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} />
            <Input label="Вес, кг"  type="number" value={weightKg} onChange={(e) => setWeightKg(e.target.value)} />
            <Input label="Год рождения" type="number" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} />

            <div>
              <label className="block text-sm font-medium text-chocolate mb-1">Пол</label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm"
              >
                {GENDERS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-chocolate mb-1">Физическая активность</label>
              <select
                value={activity}
                onChange={(e) => setActivity(e.target.value)}
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm"
              >
                {ACTIVITIES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </div>

            {/* Goal только для preset-систем */}
            {!isCustom && (
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-chocolate mb-1">Цель</label>
                <select
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm"
                >
                  {GOALS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                </select>
              </div>
            )}
          </div>
        )}

        {isCustomPercents && (
          <div className="mt-4 pt-4 border-t border-border space-y-4">
            <Input
              label="Дельта от TDEE, ккал (− дефицит / + профицит)"
              type="number"
              value={customDelta}
              onChange={(e) => setCustomDelta(e.target.value)}
            />
            <div className="grid grid-cols-3 gap-2">
              <Input label="Белки, %"   type="number" value={customPP} onChange={(e) => setCustomPP(e.target.value)} />
              <Input label="Жиры, %"    type="number" value={customFP} onChange={(e) => setCustomFP(e.target.value)} />
              <Input label="Углеводы, %" type="number" value={customCP} onChange={(e) => setCustomCP(e.target.value)} />
            </div>
            <div className={'text-xs ' + (Math.abs(pctSum - 100) > 0.5 ? 'text-red-600' : 'text-gray-500')}>
              Сумма Б/Ж/У: {pctSum.toFixed(1)}% (должна быть 100%)
            </div>
            <Input label="Клетчатка, г" type="number" value={customFib} onChange={(e) => setCustomFib(e.target.value)} />
          </div>
        )}

        {isCustomGrams && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Калории, ккал" type="number" value={customCal} onChange={(e) => setCustomCal(e.target.value)} />
            <Input label="Белки, г"      type="number" value={customP}   onChange={(e) => setCustomP(e.target.value)} />
            <Input label="Жиры, г"       type="number" value={customF}   onChange={(e) => setCustomF(e.target.value)} />
            <Input label="Углеводы, г"   type="number" value={customC}   onChange={(e) => setCustomC(e.target.value)} />
            <Input label="Клетчатка, г"  type="number" value={customFib} onChange={(e) => setCustomFib(e.target.value)} />
          </div>
        )}

        <div className="mt-5">
          <Button onClick={onCalc} loading={loading}>Рассчитать</Button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm whitespace-pre-wrap">
            {error}
          </div>
        )}
      </Card>

      {/* Result */}
      {result && (
        <Card className="p-6">
          <h2 className="text-lg font-bold text-chocolate mb-3">Результат</h2>

          {(result.bmr || result.tdee) && (
            <div className="text-sm text-gray-600 mb-4">
              {result.age != null && <>Возраст: <b>{result.age}</b> · </>}
              {result.bmr != null && <>BMR: <b>{result.bmr}</b> ккал · </>}
              {result.tdee != null && <>TDEE: <b>{result.tdee}</b> ккал</>}
            </div>
          )}

          <div className="grid grid-cols-5 gap-2">
            <div className="p-3 rounded-xl bg-tomato/10 text-tomato">
              <div className="text-xs">Ккал</div>
              <div className="font-bold text-lg">{result.calorie_target}</div>
            </div>
            <div className="p-3 rounded-xl bg-blue-50 text-blue-700">
              <div className="text-xs">Белок, г</div>
              <div className="font-bold text-lg">{parseFloat(result.protein_target_g).toFixed(0)}</div>
            </div>
            <div className="p-3 rounded-xl bg-amber-50 text-amber-700">
              <div className="text-xs">Жиры, г</div>
              <div className="font-bold text-lg">{parseFloat(result.fat_target_g).toFixed(0)}</div>
            </div>
            <div className="p-3 rounded-xl bg-emerald-50 text-emerald-700">
              <div className="text-xs">Углев, г</div>
              <div className="font-bold text-lg">{parseFloat(result.carb_target_g).toFixed(0)}</div>
            </div>
            <div className="p-3 rounded-xl bg-purple-50 text-purple-700">
              <div className="text-xs">Клетч, г</div>
              <div className="font-bold text-lg">{parseFloat(result.fiber_target_g).toFixed(0)}</div>
            </div>
          </div>

          {success ? (
            <div className="mt-5 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
              {success}
            </div>
          ) : (
            <div className="mt-5">
              <Button onClick={onApply} loading={applying}>Применить в профиль</Button>
              <p className="text-xs text-gray-500 mt-2">
                Целевые КБЖУ и исходные параметры будут сохранены в профиль. Источник: «вручную».
              </p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
