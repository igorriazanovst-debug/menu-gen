import client from './client';
import type { Menu, PaginatedResponse, ShoppingList } from '../types';

export interface DeletedMenu {
  id: number;
  menu_id: number;
  data: any;
  deleted_by_name: string | null;
  deleted_at: string;
  purge_after: string;
  can_purge: boolean;
}

export interface SwapResult {
  allergen_warning: boolean;
  allergens_found: string[];
  calorie_warning: boolean;
  recipe_calories: number;
}

export const menuApi = {
  list: () => client.get<PaginatedResponse<Menu>>('/menu/'),

  get: (id: number) => client.get<Menu>(`/menu/${id}/`),

  generate: (data: {
    period_days: number;
    start_date: string;
    country?: string;
    max_cook_time?: number;
    calorie_min?: number;
    calorie_max?: number;
  }) => client.post<Menu>('/menu/generate/', data),

  delete: (id: number) => client.delete(`/menu/${id}/delete/`),

  archive: (id: number) => client.post(`/menu/${id}/archive/`),

  quarantine: () => client.get<DeletedMenu[]>('/menu/quarantine/'),

  restore: (deletedId: number) => client.post<Menu>(`/menu/quarantine/${deletedId}/restore/`),

  swapItem: (menuId: number, itemId: number, recipeId: number) =>
    client.patch<SwapResult>(`/menu/${menuId}/items/${itemId}/`, { recipe_id: recipeId }),

  shoppingList: (menuId: number) =>
    client.get<ShoppingList>(`/menu/${menuId}/shopping-list/`),

  toggleShoppingItem: (menuId: number, itemId: number) =>
    client.patch(`/menu/${menuId}/shopping-list/items/${itemId}/toggle/`),
};

// MG-402
export async function swapMenuItem(menuId: number, itemId: number, recipeId: number) {
  const { data } = await client.patch(
    `/menu/${menuId}/items/${itemId}/`, { recipe_id: recipeId }
  );
  return data;
}
