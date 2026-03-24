import client from './client';
import type { Menu, PaginatedResponse, ShoppingList } from '../types';

export const menuApi = {
  list: () => client.get<PaginatedResponse<Menu>>('/menu/'),

  get: (id: number) => client.get<Menu>(`/menu/${id}/`),

  generate: (data: { period_days: number; start_date: string; country?: string }) =>
    client.post<Menu>('/menu/generate/', data),

  swapItem: (menuId: number, itemId: number, recipeId: number) =>
    client.patch(`/menu/${menuId}/items/${itemId}/`, { recipe_id: recipeId }),

  archive: (id: number) => client.post(`/menu/${id}/archive/`),

  shoppingList: (menuId: number) =>
    client.get<ShoppingList>(`/menu/${menuId}/shopping-list/`),

  toggleShoppingItem: (menuId: number, itemId: number) =>
    client.patch(`/menu/${menuId}/shopping-list/items/${itemId}/toggle/`),
};
