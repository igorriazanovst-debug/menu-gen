// DIARY_V2
import client from './client';
import type {
  DiaryEntry, DiaryDayStats, DiaryWaterLog, MealType,
} from '../types';

export interface DiaryListParams { date: string; member_id?: number; }
export interface DiaryCreatePayload {
  date: string;
  meal_type: MealType;
  recipe?: number;
  custom_name?: string;
  nutrition?: Record<string, { value: string; unit: string }>;
  quantity?: number;
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

  importFromMenu: (menuId: number, date: string, memberId?: number) => {
    const params: Record<string, string | number> = { menu_id: menuId, date };
    if (memberId) params.member_id = memberId;
    return client.post('/diary/import-from-menu/', null, { params });
  },

  getWater: async (date: string): Promise<DiaryWaterLog> => {
    const { data } = await client.get<DiaryWaterLog>('/diary/water/', { params: { date } });
    return data;
  },
  setWater: (date: string, water_ml: number) =>
    client.post<DiaryWaterLog>('/diary/water/', { date, water_ml }),
};
