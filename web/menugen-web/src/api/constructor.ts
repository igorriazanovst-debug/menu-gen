// MG_CONSTRUCTOR: API-клиент ручного конструктора меню.
import client from './client';
import type {
  ConstructedMenu,
  ConstructedMenuListItem,
  ConstructorClient,
} from '../types';

// Payload на сохранение (без серверных полей).
export interface ConstructedMenuPayload {
  name: string;
  client_family?: number | null;
  days: number;
  status: 'draft' | 'published';
  meals: {
    day_index: number;
    order: number;
    name: string;
    target_calories?: number | null;
    target_protein?: string | number | null;
    target_fat?: string | number | null;
    target_carbs?: string | number | null;
    items: { recipe_id: number; quantity: number }[];
  }[];
}

export const constructorApi = {
  list: () => client.get<ConstructedMenuListItem[]>('/menu/constructor/'),

  get: (id: number) => client.get<ConstructedMenu>(`/menu/constructor/${id}/`),

  create: (data: ConstructedMenuPayload) =>
    client.post<ConstructedMenu>('/menu/constructor/', data),

  update: (id: number, data: ConstructedMenuPayload) =>
    client.put<ConstructedMenu>(`/menu/constructor/${id}/`, data),

  remove: (id: number) => client.delete(`/menu/constructor/${id}/`),

  clients: () => client.get<ConstructorClient[]>('/menu/constructor/clients/'),
};
