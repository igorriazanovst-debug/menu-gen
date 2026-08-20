// MG_SPECUI: разбор клиента в карточке — неделя, рацион, исключения, вес, цели.
//
// Вкладки, а не всё сразу: пять запросов при открытии карточки — это пять
// обращений к базе ради данных, на которые специалист может и не посмотреть.
// Каждая вкладка грузится при первом открытии и потом живёт в состоянии.
import React, { useCallback, useEffect, useState } from 'react';
import {
  MemberExclusions,
  MemberRation,
  MemberSummary,
  MemberTargets,
  MemberWeight,
  specialistAnalyticsApi,
} from '../../api/specialistAnalytics';
import {
  FOOD_GROUP_LABELS,
  PROTEIN_TYPE_LABELS,
  TARGET_FIELD_LABELS,
  TARGET_SOURCE_LABELS,
  adherencePercent,
  coverageNote,
  deviationPercent,
  labelFor,
  waterPerDay,
  weightTrend,
} from '../../utils/specialistFormat';

type Tab = 'summary' | 'ration' | 'exclusions' | 'weight' | 'targets';

const TABS: { key: Tab; title: string }[] = [
  { key: 'summary', title: 'Неделя' },
  { key: 'ration', title: 'Рацион' },
  { key: 'exclusions', title: 'Исключения' },
  { key: 'weight', title: 'Вес' },
  { key: 'targets', title: 'Цели' },
];

const Card: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="bg-surface rounded-xl shadow p-4">
    <h3 className="font-semibold text-chocolate mb-2">{title}</h3>
    {children}
  </div>
);

const Stat: React.FC<{ label: string; value: React.ReactNode; hint?: string }> = ({
  label,
  value,
  hint,
}) => (
  <div>
    <p className="text-xs text-gray-400">{label}</p>
    <p className="text-lg font-semibold text-chocolate">{value}</p>
    {hint && <p className="text-xs text-gray-400">{hint}</p>}
  </div>
);

const Deviation: React.FC<{ actual: number; target: number | null; unit: string }> = ({
  actual,
  target,
  unit,
}) => {
  const dev = deviationPercent(actual, target);
  return (
    <span>
      {actual} {unit}
      {dev !== null && (
        <span className={dev > 0 ? 'text-tomato text-sm ml-1' : 'text-avocado text-sm ml-1'}>
          {dev > 0 ? '+' : ''}
          {dev}% к цели
        </span>
      )}
    </span>
  );
};

export const ClientAnalytics: React.FC<{ familyId: number }> = ({ familyId }) => {
  const [tab, setTab] = useState<Tab>('summary');
  const [summary, setSummary] = useState<MemberSummary[] | null>(null);
  const [ration, setRation] = useState<MemberRation[] | null>(null);
  const [exclusions, setExclusions] = useState<MemberExclusions[] | null>(null);
  const [weight, setWeight] = useState<MemberWeight[] | null>(null);
  const [targets, setTargets] = useState<MemberTargets[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    // Уже загруженное не перезапрашиваем при переключении вкладок.
    const loaded =
      (tab === 'summary' && summary) ||
      (tab === 'ration' && ration) ||
      (tab === 'exclusions' && exclusions) ||
      (tab === 'weight' && weight) ||
      (tab === 'targets' && targets);
    if (loaded) return;
    setBusy(true);
    try {
      if (tab === 'summary') setSummary(await specialistAnalyticsApi.summary(familyId));
      if (tab === 'ration') setRation(await specialistAnalyticsApi.ration(familyId));
      if (tab === 'exclusions') setExclusions(await specialistAnalyticsApi.exclusions(familyId));
      if (tab === 'weight') setWeight(await specialistAnalyticsApi.weight(familyId));
      if (tab === 'targets') setTargets(await specialistAnalyticsApi.targetsHistory(familyId));
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      // 403 здесь — не поломка: тренеру закрыт рацион, повару — дневник.
      setError(
        status === 403
          ? 'Ваша роль не даёт доступа к этому разделу клиента.'
          : 'Не удалось загрузить данные.',
      );
    } finally {
      setBusy(false);
    }
  }, [tab, familyId, summary, ration, exclusions, weight, targets]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section>
      <div className="flex gap-2 mb-3 flex-wrap">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm px-3 py-1.5 rounded-lg border transition ${
              tab === t.key
                ? 'bg-avocado text-white border-avocado'
                : 'text-chocolate border-gray-200 hover:border-avocado'
            }`}
          >
            {t.title}
          </button>
        ))}
      </div>

      {busy && <p className="text-sm text-gray-400">Загружаем…</p>}
      {error && <p className="text-sm text-tomato">{error}</p>}

      {!busy && !error && tab === 'summary' && (
        <div className="space-y-3">
          {(summary ?? []).map((m) => {
            const adherence = adherencePercent(m.days_on_plan, m.days_tracked);
            return (
              <Card key={m.member_id} title={m.member_name || `Участник #${m.member_id}`}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Stat
                    label={`Дней с записями из ${m.days}`}
                    value={m.days_tracked}
                    hint={adherence === null ? 'записей нет' : `по плану ${adherence}%`}
                  />
                  <Stat
                    label="Калории в день"
                    value={
                      <Deviation
                        actual={m.avg_per_tracked_day.calories}
                        target={m.targets.calories}
                        unit="ккал"
                      />
                    }
                    hint="среднее по дням с записями"
                  />
                  <Stat
                    label="Белок в день"
                    value={
                      <Deviation
                        actual={m.avg_per_tracked_day.proteins}
                        target={m.targets.proteins}
                        unit="г"
                      />
                    }
                  />
                  <Stat
                    label="Вода"
                    value={waterPerDay(m.water.total_ml, m.water.days_logged)}
                    hint={`записей: ${m.water.days_logged}`}
                  />
                </div>
                <div className="mt-3 pt-3 border-t text-sm text-gray-500">
                  Вес: {m.weight.last !== null ? `${m.weight.last} кг` : 'нет замеров'}
                  {m.weight.points > 1 && ` · ${weightTrend(m.weight.change_kg)} за период`}
                </div>
              </Card>
            );
          })}
          {(summary ?? []).length === 0 && <p className="text-sm text-gray-400">Нет данных.</p>}
        </div>
      )}

      {!busy && !error && tab === 'ration' && (
        <div className="space-y-3">
          {(ration ?? []).map((m) => {
            const note = coverageNote(m.coverage.percent);
            return (
              <Card key={m.member_id} title={m.member_name || `Участник #${m.member_id}`}>
                {note && <p className="text-xs text-tomato mb-2">{note}</p>}
                <p className="text-xs text-gray-400 mb-3">
                  Записей: {m.entries_total}, из них с рецептом {m.coverage.with_recipe} (
                  {m.coverage.percent}%)
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                  <Stat label="Дней с жирной рыбой" value={m.fatty_fish_days} />
                  <Stat label="Дней с красным мясом" value={m.red_meat_days} />
                  <Stat label="Разных блюд" value={m.variety.distinct_dishes} />
                  <Stat
                    label="Клетчатка"
                    value={`${m.fiber.total_g} г`}
                    hint={`посчитана по ${m.fiber.coverage_percent}% записей`}
                  />
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Группы продуктов</p>
                    {m.food_groups.length === 0 && <p className="text-sm text-gray-400">—</p>}
                    {m.food_groups.map((g) => (
                      <div key={g.group} className="flex justify-between text-sm text-chocolate">
                        <span>{labelFor(FOOD_GROUP_LABELS, g.group)}</span>
                        <span className="text-gray-400">
                          {g.count} · {g.percent}%
                        </span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Источники белка</p>
                    {m.protein_sources.length === 0 && <p className="text-sm text-gray-400">—</p>}
                    {m.protein_sources.map((p) => (
                      <div key={p.type} className="flex justify-between text-sm text-chocolate">
                        <span>{labelFor(PROTEIN_TYPE_LABELS, p.type)}</span>
                        <span className="text-gray-400">
                          {p.count} · {p.percent}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                {m.variety.top_repeats.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <p className="text-xs text-gray-400 mb-1">Чаще всего повторяется</p>
                    {m.variety.top_repeats.map((r) => (
                      <div key={r.title} className="flex justify-between text-sm text-chocolate">
                        <span>{r.title}</span>
                        <span className="text-gray-400">{r.count} раз</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
          {(ration ?? []).length === 0 && <p className="text-sm text-gray-400">Нет данных.</p>}
        </div>
      )}

      {!busy && !error && tab === 'exclusions' && (
        <div className="space-y-3">
          {(exclusions ?? []).map((m) => {
            const watching = [
              ...m.watching.allergens,
              ...m.watching.custom,
              ...m.watching.disliked,
            ];
            const clean = m.diary.length === 0 && m.menu.length === 0;
            return (
              <Card key={m.member_id} title={m.member_name || `Участник #${m.member_id}`}>
                <p className="text-xs text-gray-400 mb-2">
                  Проверяем: {watching.length ? watching.join(', ') : 'ограничений не задано'}
                </p>
                {clean && <p className="text-sm text-avocado">Нарушений не найдено.</p>}
                {m.menu.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-gray-400 mb-1">В активном меню</p>
                    {m.menu.map((h, i) => (
                      <div key={`${h.title}-${i}`} className="text-sm text-chocolate">
                        {h.title}{' '}
                        <span className="text-tomato text-xs">{h.reasons.join('; ')}</span>
                        <span className="text-gray-400 text-xs"> · день {(h.day_offset ?? 0) + 1}</span>
                      </div>
                    ))}
                  </div>
                )}
                {m.diary.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 mb-1">В дневнике</p>
                    {m.diary.map((h, i) => (
                      <div key={`${h.title}-${i}`} className="text-sm text-chocolate">
                        {h.date} — {h.title}{' '}
                        <span className="text-tomato text-xs">{h.reasons.join('; ')}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
          {(exclusions ?? []).length === 0 && <p className="text-sm text-gray-400">Нет данных.</p>}
        </div>
      )}

      {!busy && !error && tab === 'weight' && (
        <div className="space-y-3">
          {(weight ?? []).map((m) => (
            <Card key={m.member_id} title={m.member_name || `Участник #${m.member_id}`}>
              {m.points.length === 0 ? (
                <p className="text-sm text-gray-400">
                  Замеров нет. Клиент вносит вес в дневнике.
                </p>
              ) : (
                <div className="space-y-1">
                  {m.points.map((p) => (
                    <div key={p.date} className="flex justify-between text-sm text-chocolate">
                      <span className="text-gray-400">{p.date}</span>
                      <span>
                        {p.weight_kg} кг {p.note && <span className="text-gray-400">· {p.note}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
          {(weight ?? []).length === 0 && <p className="text-sm text-gray-400">Нет данных.</p>}
        </div>
      )}

      {!busy && !error && tab === 'targets' && (
        <div className="space-y-3">
          {(targets ?? []).map((m) => (
            <Card key={m.member_id} title={m.member_name || `Участник #${m.member_id}`}>
              {m.changes.length === 0 ? (
                <p className="text-sm text-gray-400">Правок не было.</p>
              ) : (
                <div className="space-y-1">
                  {m.changes.map((c, i) => (
                    <div key={`${c.field}-${c.at}-${i}`} className="text-sm text-chocolate">
                      <span className="text-gray-400">{c.at.slice(0, 10)}</span>{' '}
                      {labelFor(TARGET_FIELD_LABELS, c.field)}:{' '}
                      {c.old_value !== null ? c.old_value : '—'} → {c.new_value ?? '—'}{' '}
                      <span className="text-xs text-gray-400">
                        ({labelFor(TARGET_SOURCE_LABELS, c.source)}
                        {c.by ? `, ${c.by}` : ''})
                      </span>
                      {c.reason && <span className="text-xs text-gray-400"> · {c.reason}</span>}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
          {(targets ?? []).length === 0 && <p className="text-sm text-gray-400">Нет данных.</p>}
        </div>
      )}
    </section>
  );
};
