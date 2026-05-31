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

// MG_607_V_api: расширенный generate
export interface GenerateMenuPayload {
  period_days: number;
  start_date: string;
  meal_plan_type?: '3' | '5';
  country?: string;                 // legacy single
  countries?: string[];             // MG-607: мульти
  max_cook_time?: number;
  exclude_allergens?: string[];     // MG-607: [] = выкл фильтр; undefined = из profile
  exclude_disliked?: string[];      // MG-607: то же
  member_ids?: number[];
  mode?: 'per_member' | 'family';
  with_soup?: boolean;             // MG_610_V_web: include soup in lunch
}

export const menuApi = {
  list: () => client.get<PaginatedResponse<Menu>>('/menu/'),

  get: (id: number) => client.get<Menu>(`/menu/${id}/`),

  generate: (data: GenerateMenuPayload) => client.post<Menu>('/menu/generate/', data),

  delete: (id: number) => client.delete(`/menu/${id}/delete/`),

  archive: (id: number) => client.post(`/menu/${id}/archive/`),

  quarantine: () => client.get<DeletedMenu[]>('/menu/quarantine/'),

  restore: (deletedId: number) => client.post<Menu>(`/menu/quarantine/${deletedId}/restore/`),

  // MG_608_V_api
  purge: (deletedId: number) => client.delete(`/menu/quarantine/${deletedId}/purge/`),

  purgeAll: () => client.delete<{ deleted: number }>(`/menu/quarantine/purge-all/`),

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
