// MG_205UI_V_profile_page = 1
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom'; // MG_206_V_profile_btn
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { setUser } from '../../store/slices/authSlice';
import { authApi } from '../../api/auth';
import { familyApi } from '../../api/family';
import { usersApi } from '../../api/users';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { SkinSwitcher } from '../../components/ui/SkinSwitcher'; // MG_SKIN
import { TargetField, type TargetLoader } from '../../components/profile/TargetField';
import { AllergenEditor } from '../../components/profile/AllergenEditor'; // MG_ALLERGEN
import { getErrorMessage } from '../../utils/api';
import { // MG_NUTRIDETAIL + MG_FOODSCALE
  FOOD_SCALE_OPTIONS, NUTRITION_DETAIL_OPTIONS, detailOf, macrosShort, scaleFactor,
  scaleOf, showsGrams, showsMacros,
  type FoodTextScale, type NutritionDetail,
} from '../../utils/nutritionDetail';
import type {
  MealPlan,
  NutritionTargets,
  UserProfile,
  TargetField as TF,
  TargetsMeta,
  Family, // MG_RUBRIC007
} from '../../types';

const CURRENCY_OPTIONS = [
  { value: 'RUB', label: '₽ Рубль (RUB)' },
  { value: 'USD', label: '$ Доллар (USD)' },
  { value: 'EUR', label: '€ Евро (EUR)' },
];

const MEAL_PLAN_OPTIONS: { value: MealPlan; label: string; hint: string }[] = [
  { value: '3', label: '3 приёма', hint: 'завтрак / обед / ужин' },
  { value: '5', label: '5 приёмов', hint: '+ перекусы между ними' },
];

export const ProfilePage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate(); // MG_206_V_profile_btn
  const user = useAppSelector((s) => s.auth.user);

  const [name, setName]   = useState(user?.name ?? '');
  const [mealPlan, setMealPlan] = useState<MealPlan>(user?.profile?.meal_plan_type ?? '3');
  // MG_ALLERGEN: список аллергенов пользователя (сохраняется отдельно, on change).
  const [allergies, setAllergies] = useState<string[]>(user?.allergies ?? []);
  const [allergenSaving, setAllergenSaving] = useState(false);
  const [allergenMsg, setAllergenMsg] = useState('');
  // MG_RUBRIC007_state: family currency.
  const [family, setFamily] = useState<Family | null>(null);
  const [currency, setCurrency] = useState('RUB');
  const [curSaving, setCurSaving] = useState(false);
  const [curMsg, setCurMsg] = useState('');
  // MG_SHELFLIFE: подставлять ли сроки годности при переносе покупок.
  const [autoExpiry, setAutoExpiry] = useState(true);
  const [expSaving, setExpSaving] = useState(false);
  const [expMsg, setExpMsg] = useState('');
  // MG_HEADKEEPS: разрешение главе семьи править мои записи в дневнике.
  const [headMayEdit, setHeadMayEdit] = useState(!!user?.profile?.head_may_edit_diary);
  const [headMsg, setHeadMsg] = useState('');
  const [headSaving, setHeadSaving] = useState(false);
  // MG_NUTRIDETAIL: подробность чисел в списках еды. Сохраняется сразу, как
  // аллергены: настройка отображения — не та вещь, ради которой жмут «Сохранить».
  const [detail, setDetail] = useState<NutritionDetail>(detailOf(user?.profile));
  const [detailSaving, setDetailSaving] = useState(false);
  const [detailMsg, setDetailMsg] = useState('');
  // MG_FOODSCALE: размер шрифта в списках еды.
  const [foodScale, setFoodScale] = useState<FoodTextScale>(scaleOf(user?.profile));
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError]     = useState('');

  useEffect(() => {
    setName(user?.name ?? '');
    setMealPlan(user?.profile?.meal_plan_type ?? '3');
    setAllergies(user?.allergies ?? []);
    setHeadMayEdit(!!user?.profile?.head_may_edit_diary); // MG_HEADKEEPS
    setDetail(detailOf(user?.profile)); // MG_NUTRIDETAIL
    setFoodScale(scaleOf(user?.profile)); // MG_FOODSCALE
  }, [user?.id, user?.name, user?.profile?.meal_plan_type, user?.allergies,
      user?.profile?.head_may_edit_diary, user?.profile?.nutrition_detail,
      user?.profile?.food_text_scale]);

  // MG_RUBRIC007_load: fetch family to read/set its currency.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await familyApi.get();
        if (cancelled) return;
        setFamily(data);
        setCurrency(data.currency ?? 'RUB');
        setAutoExpiry(data.auto_expiry !== false); // MG_SHELFLIFE
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  const isOwner = !!family && !!user && family.owner_name === user.name;

  const saveCurrency = async () => {
    setCurSaving(true);
    setCurMsg('');
    try {
      const { data } = await familyApi.update({ currency });
      setFamily(data);
      setCurMsg('Валюта обновлена!');
    } catch (e) {
      setCurMsg(getErrorMessage(e));
    } finally {
      setCurSaving(false);
    }
  };

  // MG_SHELFLIFE: сохраняем сразу — галочка без кнопки «сохранить» врёт реже,
  // чем с ней: видимое состояние всегда равно серверному.
  const saveAutoExpiry = async (next: boolean) => {
    const prev = autoExpiry;
    setAutoExpiry(next);
    setExpSaving(true);
    setExpMsg('');
    try {
      const { data } = await familyApi.update({ auto_expiry: next });
      setFamily(data);
      setExpMsg(next ? 'Сроки будут подставляться.' : 'Сроки проставляются вручную.');
    } catch (e) {
      setAutoExpiry(prev);
      setExpMsg(getErrorMessage(e));
    } finally {
      setExpSaving(false);
    }
  };

  const targets: NutritionTargets | null = useMemo(() => {
    const p = user?.profile;
    if (!p) return null;
    if (p.calorie_target && p.protein_target_g) {
      return {
        calorie_target:   p.calorie_target,
        protein_target_g: String(p.protein_target_g),
        fat_target_g:     String(p.fat_target_g ?? ''),
        carb_target_g:    String(p.carb_target_g ?? ''),
        fiber_target_g:   String(p.fiber_target_g ?? ''),
      };
    }
    return p.targets_calculated ?? null;
  }, [user?.profile]);

  const meta: TargetsMeta = user?.profile?.targets_meta ?? {};

  const profileFilled = !!(user?.profile?.birth_year && user?.profile?.height_cm && user?.profile?.weight_kg);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setSuccess(''); setError('');
    try {
      const payload: Partial<UserProfile> = { meal_plan_type: mealPlan };
      const { data } = await authApi.updateMe({ name, profile: payload });
      dispatch(setUser(data));
      setSuccess('Профиль обновлён!');
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setSaving(false); }
  };

  // MG_NUTRIDETAIL: сохранить подробность чисел сразу при выборе.
  const saveDetail = useCallback(async (next: NutritionDetail) => {
    const prev = detail;
    setDetail(next);
    setDetailSaving(true);
    setDetailMsg('');
    try {
      const { data } = await authApi.updateMe({ profile: { nutrition_detail: next } });
      dispatch(setUser(data));
      setDetailMsg('Сохранено');
    } catch (e) {
      // Вернуть показ назад обязательно: настройка отображения, которая не
      // сохранилась, не должна выглядеть применённой.
      setDetail(prev);
      setDetailMsg(getErrorMessage(e));
    } finally {
      setDetailSaving(false);
    }
  }, [detail, dispatch]);

  // MG_FOODSCALE: размер шрифта сохраняется сразу, как и подробность.
  const saveFoodScale = useCallback(async (next: FoodTextScale) => {
    const prev = foodScale;
    setFoodScale(next);
    setDetailSaving(true);
    setDetailMsg('');
    try {
      const { data } = await authApi.updateMe({ profile: { food_text_scale: next } });
      dispatch(setUser(data));
      setDetailMsg('Сохранено');
    } catch (e) {
      setFoodScale(prev);
      setDetailMsg(getErrorMessage(e));
    } finally {
      setDetailSaving(false);
    }
  }, [foodScale, dispatch]);

  // MG_ALLERGEN: сохранить список аллергенов сразу при изменении (оптимистично).
  const saveAllergies = useCallback(async (next: string[]) => {
    const prev = allergies;
    setAllergies(next);
    setAllergenSaving(true);
    setAllergenMsg('');
    try {
      const { data } = await authApi.updateMe({ allergies: next });
      dispatch(setUser(data));
      setAllergenMsg('Аллергены сохранены');
    } catch (e) {
      setAllergies(prev);
      setAllergenMsg(getErrorMessage(e));
    } finally {
      setAllergenSaving(false);
    }
  }, [allergies, dispatch]);

  // MG_HEADKEEPS: согласие даёт сам человек, поэтому сохраняем сразу и здесь —
  // в своём профиле. Через семейную ручку это поле не проходит: иначе глава
  // выдал бы разрешение себе сам, а такое согласие ни от чего не защищает.
  const saveHeadMayEdit = useCallback(async (next: boolean) => {
    const prev = headMayEdit;
    setHeadMayEdit(next);
    setHeadSaving(true);
    setHeadMsg('');
    try {
      const { data } = await authApi.updateMe({ profile: { head_may_edit_diary: next } });
      dispatch(setUser(data));
      setHeadMsg(next ? 'Глава семьи может править ваши записи' : 'Правки главы семьи запрещены');
    } catch (e) {
      setHeadMayEdit(prev);
      setHeadMsg(getErrorMessage(e));
    } finally {
      setHeadSaving(false);
    }
  }, [headMayEdit, dispatch]);

  const reloadMe = useCallback(async () => {
    try {
      const { data } = await authApi.me();
      dispatch(setUser(data));
    } catch { /* ignore */ }
  }, [dispatch]);

  // TargetLoader для текущего пользователя
  const meLoader: TargetLoader = useMemo(() => ({
    getHistory: async (f: TF) => (await usersApi.getTargetHistory(f)).data,
    reset:      async (f: TF) => { await usersApi.resetTarget(f); await reloadMe(); },
  }), [reloadMe]);

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold text-chocolate">Профиль</h1>

      <Card className="p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-tomato/10 flex items-center justify-center text-3xl font-bold text-tomato">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div>
            <p className="font-semibold text-chocolate text-lg">{user?.name}</p>
            <p className="text-sm text-gray-500">{user?.email ?? user?.phone}</p>
          </div>
        </div>

        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <Input label="Имя" value={name} onChange={(e) => setName(e.target.value)} error={error} />
          <EmailSection />

          <div>
            <label className="block text-sm font-medium text-chocolate mb-2">
              План приёмов пищи
            </label>
            <div className="grid grid-cols-2 gap-2">
              {MEAL_PLAN_OPTIONS.map((opt) => {
                const active = mealPlan === opt.value;
                return (
                  <button
                    type="button"
                    key={opt.value}
                    onClick={() => setMealPlan(opt.value)}
                    className={
                      'p-3 rounded-xl border text-left transition ' +
                      (active
                        ? 'border-tomato bg-tomato/10 text-chocolate'
                        : 'border-border bg-surface hover:border-tomato/50 text-gray-700')
                    }
                  >
                    <div className="font-semibold">{opt.label}</div>
                    <div className="text-xs opacity-70">{opt.hint}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <Button type="submit" loading={saving}>Сохранить</Button>
        </form>

        {/* MG_RUBRIC007_ui: family currency */}
        <div className="mt-6 pt-6 border-t border-border">
          <label className="block text-sm font-medium text-chocolate mb-2">
            Валюта семьи (для списков покупок)
          </label>
          <div className="flex items-center gap-2">
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              disabled={!isOwner}
              className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
            >
              {CURRENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {isOwner && (
              <Button type="button" onClick={saveCurrency} loading={curSaving}>
                Сохранить
              </Button>
            )}
          </div>
          {!isOwner && (
            <p className="text-xs text-gray-400 mt-1">Менять валюту может только глава семьи.</p>
          )}
          {curMsg && <p className="text-xs text-gray-500 mt-1">{curMsg}</p>}
        </div>

        {/* MG_SHELFLIFE: подстановка сроков годности при переносе покупок.
            Настройка семейная: холодильник общий, и режим не должен зависеть
            от того, кто сегодня разбирает пакеты. */}
        <div className="mt-6 pt-6 border-t border-border">
          <label className="flex items-start gap-2 text-sm text-chocolate">
            <input
              type="checkbox"
              checked={autoExpiry}
              disabled={!isOwner || expSaving}
              onChange={(e) => saveAutoExpiry(e.target.checked)}
              className="mt-0.5 accent-tomato"
            />
            <span>
              Подставлять сроки годности при переносе покупок в холодильник
              <span className="block text-xs text-gray-500">
                Дата считается от дня покупки по справочным срокам и показывается
                в окне переноса — её всегда можно поправить или стереть.
              </span>
            </span>
          </label>
          {!isOwner && (
            <p className="text-xs text-gray-400 mt-1">Менять настройку может только глава семьи.</p>
          )}
          {expMsg && <p className="text-xs text-gray-500 mt-1">{expMsg}</p>}
        </div>

        {/* MG_NUTRIDETAIL: сколько чисел показывать в списках еды. Настройка
            общая для веба и приложения — она в аккаунте. */}
        <div className="mt-6 pt-6 border-t border-border">
          <p className="text-sm font-semibold text-chocolate">Числа в списках еды</p>
          <p className="text-xs text-gray-500 mt-0.5">
            Дневник, меню, рецепты и подсказки при добавлении. Настройка
            синхронизируется с приложением через ваш аккаунт.
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            {NUTRITION_DETAIL_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                disabled={detailSaving}
                onClick={() => saveDetail(o.value)}
                className={`px-3 py-1.5 rounded-xl text-sm border transition-colors ${
                  detail === o.value
                    ? 'border-avocado bg-avocado/10 text-avocado font-semibold'
                    : 'border-gray-300 text-gray-600 hover:border-avocado'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {NUTRITION_DETAIL_OPTIONS.find((o) => o.value === detail)?.hint}
          </p>
          <p className="text-sm font-semibold text-chocolate mt-4">Размер шрифта</p>
          <div className="flex flex-wrap gap-2 mt-2">
            {FOOD_SCALE_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                disabled={detailSaving}
                onClick={() => saveFoodScale(o.value)}
                className={`px-3 py-1.5 rounded-xl text-sm border transition-colors ${
                  foodScale === o.value
                    ? 'border-avocado bg-avocado/10 text-avocado font-semibold'
                    : 'border-gray-300 text-gray-600 hover:border-avocado'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          {/* Строка-образец: ровно так запись выглядит в дневнике при этом
              выборе. Проверять настройку, уходя в дневник и обратно, — лишний
              путь. */}
          <div className="mt-2 rounded-xl bg-rice px-3 py-2 flex items-center justify-between gap-3"
               style={{ fontSize: `${scaleFactor(foodScale)}em` }}>
            <span className="min-w-0">
              <span className="block text-[1em] text-chocolate truncate">Овсянка на молоке</span>
              {(showsGrams(detail) || showsMacros(detail)) && (
                <span className="block text-[0.78em] text-gray-500 truncate">
                  {[showsGrams(detail) ? '250 г' : '', showsMacros(detail) ? macrosShort(12, 8, 30) : '']
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              )}
            </span>
            <span className="text-[0.85em] font-semibold text-avocado shrink-0">412 ккал</span>
          </div>
          {detailMsg && <p className="text-xs text-gray-500 mt-1">{detailMsg}</p>}
        </div>

        {/* MG_HEADKEEPS: кто ведёт мой дневник. Добавлять записи глава семьи
            может и без разрешения — они помечены короной, видно, кто внёс.
            Разрешение здесь — про правку и удаление уже записанного. */}
        <div className="mt-6 pt-6 border-t border-border">
          <label className="flex items-start gap-2 text-sm text-chocolate">
            <input
              type="checkbox"
              checked={headMayEdit}
              disabled={headSaving}
              onChange={(e) => saveHeadMayEdit(e.target.checked)}
              className="mt-0.5 accent-tomato"
            />
            <span>
              Разрешить главе семьи править и удалять мои записи
              <span className="block text-xs text-gray-500">
                Добавлять записи за вас глава семьи может всегда — рядом с такой
                записью стоит корона и видно, кто её внёс. Эта галочка — про
                правку и удаление того, что записали вы сами.
              </span>
            </span>
          </label>
          {headMsg && <p className="text-xs text-gray-500 mt-1">{headMsg}</p>}
        </div>
      </Card>

      {/* MG_ALLERGEN14: аллергены пользователя (список 14 по ТР ТС 022) */}
      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-1">Аллергены</h2>
        <p className="text-xs text-gray-500 mb-4">
          Отметьте аллергены из обязательного перечня (ТР ТС 022/2011) — блюда с ними
          исключаются из генерации меню. Можно добавить и свой аллерген вне списка.
        </p>
        <AllergenEditor value={allergies} onChange={saveAllergies} />
        {allergenSaving ? (
          <p className="text-xs text-gray-400 mt-2">Сохранение…</p>
        ) : (
          allergenMsg && <p className="text-xs text-gray-500 mt-2">{allergenMsg}</p>
        )}
      </Card>

      {/* MG_SKIN: выбор скина оформления */}
      <Card className="p-6">
        <h2 className="text-lg font-bold text-text mb-1">Оформление</h2>
        <p className="text-xs text-muted mb-4">
          Скин синхронизируется с мобильным приложением через ваш аккаунт.
        </p>
        <SkinSwitcher />
      </Card>

      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-1">Целевые КБЖУ</h2>
        <p className="text-xs text-gray-500 mb-4">
          Бейдж показывает источник правки: <span className="font-medium">auto</span> — рассчитано формулой,
          {' '}<span className="font-medium">вручную</span> — вы изменили сами,
          {' '}<span className="font-medium">специалист</span> — поставил ваш диетолог.
          Нажмите на бейдж, чтобы увидеть историю и сбросить к авто.
        </p>

        {/* MG_206_V_profile_btn: кнопка калькулятора КБЖУ */}
        <div className="mb-4">
          <button
            type="button"
            onClick={() => navigate('/profile/kbju-calculator')}
            className="px-4 py-2 rounded-xl bg-avocado text-white text-sm font-semibold hover:bg-green-700 transition"
          >
            🧮 Открыть калькулятор КБЖУ
          </button>
          <p className="text-xs text-gray-500 mt-2">
            Подберите свои целевые калории и БЖУ по выбранной системе (Mifflin-St Jeor, Harris-Benedict,
            Роспотребнадзор, EFSA) или введите значения вручную.
          </p>
        </div>

        {!profileFilled && (
          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-yellow-800 text-sm">
            Заполните параметры через калькулятор — после этого появятся целевые КБЖУ.
          </div>
        )}

        {profileFilled && targets && (
          <div className="grid grid-cols-5 gap-2">
            <TargetField label="Ккал"  unit="ккал" value={targets.calorie_target}    field="calorie_target"    meta={meta.calorie_target}    bgClass="bg-tomato/10 text-tomato"           loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Белок" unit="г"    value={targets.protein_target_g}  field="protein_target_g"  meta={meta.protein_target_g}  bgClass="bg-blue-50 text-blue-700"           loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Жиры"  unit="г"    value={targets.fat_target_g}      field="fat_target_g"      meta={meta.fat_target_g}      bgClass="bg-amber-50 text-amber-700"         loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Углев" unit="г"    value={targets.carb_target_g}     field="carb_target_g"     meta={meta.carb_target_g}     bgClass="bg-emerald-50 text-emerald-700"     loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Клетч" unit="г"    value={targets.fiber_target_g}    field="fiber_target_g"    meta={meta.fiber_target_g}    bgClass="bg-purple-50 text-purple-700"       loader={meLoader} onResetDone={reloadMe} />
          </div>
        )}

        {profileFilled && !targets && (
          <p className="text-sm text-gray-500">Не удалось рассчитать цели — проверьте параметры профиля.</p>
        )}
      </Card>
    </div>
  );
};

// MG_EMAILVERIFY: добавление/смена e-mail в профиле с подтверждением по ссылке.
const EmailSection: React.FC = () => {
  const user = useAppSelector((s) => s.auth.user);
  const dispatch = useAppDispatch();
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const hasEmail = !!user?.email;
  const verified = !!user?.email_verified;

  const submit = async () => {
    setErr(null);
    setMsg(null);
    const value = email.trim();
    if (!value) {
      setErr('Введите e-mail.');
      return;
    }
    setBusy(true);
    try {
      const { data } = await authApi.setEmail(value);
      const { data: me } = await authApi.me();
      dispatch(setUser(me));
      setEditing(false);
      setEmail('');
      setMsg(data.detail || 'Письмо со ссылкой отправлено — подтвердите e-mail.');
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.response?.data?.email?.[0] || 'Не удалось сохранить e-mail.');
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (!user?.email) return;
    setErr(null);
    setMsg(null);
    try {
      await authApi.resendVerification(user.email);
      setMsg('Письмо отправлено повторно.');
    } catch {
      setErr('Не удалось отправить письмо.');
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-chocolate mb-1">E-mail</label>
      {hasEmail && !editing ? (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-700 flex-1 min-w-[10rem]">{user!.email}</span>
          {verified ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-200">
              ✓ подтверждён
            </span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              не подтверждён
            </span>
          )}
          <button
            type="button"
            onClick={() => { setEditing(true); setEmail(user!.email || ''); setMsg(null); setErr(null); }}
            className="text-xs text-tomato hover:underline"
          >
            изменить
          </button>
        </div>
      ) : (
        <div className="flex gap-2 items-start">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="flex-1"
          />
          <Button type="button" onClick={submit} loading={busy}>Сохранить</Button>
          {hasEmail && (
            <Button type="button" variant="ghost" onClick={() => { setEditing(false); setErr(null); }}>
              Отмена
            </Button>
          )}
        </div>
      )}
      {hasEmail && !verified && !editing && (
        <button type="button" onClick={resend} className="mt-1 text-xs text-tomato hover:underline">
          Отправить письмо подтверждения снова
        </button>
      )}
      {msg && <p className="mt-1 text-xs text-green-600">{msg}</p>}
      {err && <p className="mt-1 text-xs text-red-600">{err}</p>}
    </div>
  );
};
