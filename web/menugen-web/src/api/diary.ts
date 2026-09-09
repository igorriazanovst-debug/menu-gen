// DIARY_V2
import client from './client';
import type {
  DiaryEntry, DiaryDayStats, DiaryWaterLog, MealType, MealSlot,
} from '../types';

import type { ImportResponse } from '../utils/importOutcome';

// MG_TRAINER: точка замера веса.
export interface DiaryWeightPoint {
  id: number;
  date: string;
  weight_kg: string;
  note: string;
  added_by?: number | null; // MG_HEADKEEPS
  added_by_name?: string | null;
}

// MG_BODYSIZE: обхваты тела за дату. Все пять необязательны — кто-то меряет
// только талию, и заставлять его выдумывать шею неправильно.
export interface DiaryMeasurement {
  id: number;
  date: string;
  neck_cm: string | null;
  chest_cm: string | null;
  under_bust_cm: string | null;
  waist_cm: string | null;
  hips_cm: string | null;
  note: string;
  added_by?: number | null; // MG_HEADKEEPS
  added_by_name?: string | null;
}

// Поля обхватов сверху вниз по телу: в этом порядке они и показываются, и
// один список на весь фронт бережёт от разъезда подписей и значений.
export const MEASUREMENT_FIELDS = [
  { key: 'neck_cm', label: 'Шея' },
  { key: 'chest_cm', label: 'Грудь' },
  { key: 'under_bust_cm', label: 'Под грудью' },
  { key: 'waist_cm', label: 'Талия' },
  { key: 'hips_cm', label: 'Бёдра' },
] as const;

export type MeasurementField = (typeof MEASUREMENT_FIELDS)[number]['key'];

export interface MeasurementPayload {
  date: string;
  neck_cm?: string | null;
  chest_cm?: string | null;
  under_bust_cm?: string | null;
  waist_cm?: string | null;
  hips_cm?: string | null;
  note?: string;
}

// DIARY_MULTIDAY: одиночная дата (date) ИЛИ диапазон (from/to). page_size — чтобы
// диапазон уместился в одну страницу (бэкенд: PageNumberPagination, default 20).
export interface DiaryListParams {
  date?: string;
  from?: string;
  to?: string;
  page_size?: number;
  member_id?: number;
}
export interface DiaryCreatePayload {
  date: string;
  // MG_MEALSLOT: слота достаточно — род еды сервер выведет из него сам.
  // meal_type оставлен необязательным: им пользуются старые вызовы.
  meal_slot?: MealSlot;
  meal_type?: MealType;
  recipe?: number;
  custom_name?: string;
  nutrition?: Record<string, { value: string; unit: string }>;
  quantity?: number;
  grams?: number | null; // MG_DIARYGRAMS
  is_eaten?: boolean;
}

const unwrap = <T,>(data: unknown): T[] => {
  if (Array.isArray(data)) return data as T[];
  const d = data as { results?: T[] } | null;
  return Array.isArray(d?.results) ? (d!.results as T[]) : [];
};

export const diaryApi = {
  list: async (params: DiaryListParams): Promise<DiaryEntry[]> => {
    const { data } = await client.get('/diary/', { params });
    return unwrap<DiaryEntry>(data);
  },
  create: (payload: DiaryCreatePayload, memberId?: number) =>
    client.post<DiaryEntry>('/diary/', payload, {
      params: memberId ? { member_id: memberId } : undefined,
    }),
  patch: (id: number, payload: Partial<DiaryCreatePayload>) =>
    client.patch<DiaryEntry>(`/diary/${id}/`, payload),
  remove: (id: number) => client.delete(`/diary/${id}/`),

  stats: async (from: string, to: string, memberId?: number): Promise<DiaryDayStats[]> => {
    const params: Record<string, string | number> = { from, to };
    if (memberId) params.member_id = memberId;
    const { data } = await client.get('/diary/stats/', { params });
    return Array.isArray(data) ? (data as DiaryDayStats[]) : [];
  },

  // FILL_FROM_MENU_V4: itemIds optional (subset of menu items); empty/undefined = whole menu.
  importFromMenu: (menuId: number, date: string, memberId?: number, itemIds?: number[]) => {
    const params: Record<string, string | number> = { menu_id: menuId, date };
    if (memberId) params.member_id = memberId;
    const body = itemIds && itemIds.length ? { item_ids: itemIds } : null;
    // FILL_FROM_MENU_V5: ответ типизирован — по нему видно, что создалось и куда легло.
    return client.post<ImportResponse>('/diary/import-from-menu/', body, { params });
  },

  // MG_HEADKEEPS: memberId — вода участника, которую смотрит (и ставит) глава семьи.
  getWater: async (date: string, memberId?: number): Promise<DiaryWaterLog> => {
    const params: Record<string, string | number> = { date };
    if (memberId) params.member_id = memberId;
    const { data } = await client.get<DiaryWaterLog>('/diary/water/', { params });
    return data;
  },
  setWater: (date: string, water_ml: number, memberId?: number) =>
    client.post<DiaryWaterLog>('/diary/water/', { date, water_ml },
      { params: memberId ? { member_id: memberId } : undefined },
    ),
  // MG_DAYFIX: убрать отметку за день — ошиблись днём или человеком. Строка на
  // дату одна, поэтому адресуем её датой, а не идентификатором.
  deleteWater: (date: string, memberId?: number) =>
    client.delete('/diary/water/', { params: { date, ...(memberId ? { member_id: memberId } : {}) } }),

  // MG_TRAINER: вес по датам — история, а не одно число в профиле.
  getWeight: async (days = 90, memberId?: number): Promise<DiaryWeightPoint[]> => {
    const params: Record<string, number> = { days };
    if (memberId) params.member_id = memberId;
    const { data } = await client.get<DiaryWeightPoint[]>('/diary/weight/', { params });
    return Array.isArray(data) ? data : [];
  },
  setWeight: (date: string, weight_kg: string, note = '', memberId?: number) =>
    client.post<DiaryWeightPoint>('/diary/weight/', { date, weight_kg, note },
      { params: memberId ? { member_id: memberId } : undefined },
    ),
  deleteWeight: (date: string, memberId?: number) => // MG_DAYFIX
    client.delete('/diary/weight/', { params: { date, ...(memberId ? { member_id: memberId } : {}) } }),

  // MG_BODYSIZE: обхваты по датам — рядом с весом и по тем же правилам доступа.
  getMeasurements: async (days = 180, memberId?: number): Promise<DiaryMeasurement[]> => {
    const params: Record<string, number> = { days };
    if (memberId) params.member_id = memberId;
    const { data } = await client.get<DiaryMeasurement[]>('/diary/measurements/', { params });
    return Array.isArray(data) ? data : [];
  },
  setMeasurement: (payload: MeasurementPayload, memberId?: number) =>
    client.post<DiaryMeasurement>('/diary/measurements/', payload,
      { params: memberId ? { member_id: memberId } : undefined },
    ),
  deleteMeasurement: (date: string, memberId?: number) => // MG_DAYFIX
    client.delete('/diary/measurements/', { params: { date, ...(memberId ? { member_id: memberId } : {}) } }),

  // DIARY_COPY_V3: copy selected entries into target day as plan.
  copy: (entryIds: number[], targetDate: string, memberId?: number) =>
    client.post<DiaryEntry[]>('/diary/copy/',
      { entry_ids: entryIds, target_date: targetDate },
      { params: memberId ? { member_id: memberId } : undefined },
    ),
};
