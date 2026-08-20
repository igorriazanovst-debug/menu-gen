// MG_SPECUI: аналитика по клиенту в кабинете специалиста.
//
// Пять разных ответов бэкенда, но обращение к ним одинаковое: раздел + период.
// Держим их вместе, чтобы карточка клиента не собирала URL руками.
import client from './client';

export interface MemberSummary {
  member_id: number;
  member_name: string;
  days: number;
  days_tracked: number;
  days_on_plan: number;
  entries_total: number;
  entries_eaten: number;
  avg_per_tracked_day: { calories: number; proteins: number; fats: number; carbs: number };
  targets: { calories: number | null; proteins: number | null; fats: number | null; carbs: number | null };
  water: { total_ml: number; days_logged: number };
  weight: {
    first: number | null;
    last: number | null;
    last_date: string | null;
    change_kg: number | null;
    points: number;
  };
}

export interface WeightPoint {
  date: string;
  weight_kg: number;
  note: string;
}

export interface MemberWeight {
  member_id: number;
  member_name: string;
  points: WeightPoint[];
}

export interface TargetChange {
  field: string;
  source: string;
  by: string | null;
  old_value: number | null;
  new_value: number | null;
  reason: string;
  at: string;
}

export interface MemberTargets {
  member_id: number;
  member_name: string;
  changes: TargetChange[];
}

export interface MemberRation {
  member_id: number;
  member_name: string;
  days: number;
  entries_total: number;
  coverage: { with_recipe: number; manual: number; percent: number };
  food_groups: { group: string; count: number; percent: number }[];
  protein_sources: { type: string; count: number; percent: number }[];
  fatty_fish_days: number;
  red_meat_days: number;
  variety: { distinct_dishes: number; top_repeats: { title: string; count: number }[] };
  fiber: { total_g: number; entries_counted: number; coverage_percent: number };
}

export interface ExclusionHit {
  title: string;
  reasons: string[];
  date?: string;
  menu_id?: number;
  day_offset?: number;
}

export interface MemberExclusions {
  member_id: number;
  member_name: string;
  watching: { allergens: string[]; custom: string[]; disliked: string[] };
  diary: ExclusionHit[];
  menu: ExclusionHit[];
}

const cabinet = (familyId: number, path: string) =>
  `/specialists/cabinet/clients/${familyId}/${path}`;

export const specialistAnalyticsApi = {
  summary: async (familyId: number, days = 7): Promise<MemberSummary[]> => {
    const { data } = await client.get(cabinet(familyId, 'summary/'), { params: { days } });
    return data.members ?? [];
  },
  weight: async (familyId: number, days = 90): Promise<MemberWeight[]> => {
    const { data } = await client.get(cabinet(familyId, 'weight/'), { params: { days } });
    return data.members ?? [];
  },
  targetsHistory: async (familyId: number): Promise<MemberTargets[]> => {
    const { data } = await client.get(cabinet(familyId, 'targets-history/'));
    return data.members ?? [];
  },
  ration: async (familyId: number, days = 14): Promise<MemberRation[]> => {
    const { data } = await client.get(cabinet(familyId, 'ration/'), { params: { days } });
    return data.members ?? [];
  },
  exclusions: async (familyId: number, days = 14): Promise<MemberExclusions[]> => {
    const { data } = await client.get(cabinet(familyId, 'exclusions/'), { params: { days } });
    return data.members ?? [];
  },
};

// MG_MENUAPPLY: выдать составленное меню клиенту.
export const applyConstructedMenu = (menuId: number, startDate?: string) =>
  client.post<{ menu_id: number; start_date: string; end_date: string; items: number }>(
    `/menu/constructor/${menuId}/apply/`,
    startDate ? { start_date: startDate } : {},
  );
